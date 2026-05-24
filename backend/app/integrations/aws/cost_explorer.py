from __future__ import annotations
"""AWS Cost Explorer — fetches real cost data by service, region, and time period."""
from datetime import date, timedelta
from app.integrations.aws.client import AWSClient


class CostExplorer(AWSClient):

    async def get_monthly_costs(self, months: int = 6) -> list[dict]:
        """Total cost per month — used for trend line."""
        try:
            ce = self.get_session().client("ce")
            end = date.today().replace(day=1)          # start of this month
            start = (end - timedelta(days=months * 31)).replace(day=1)

            response = ce.get_cost_and_usage(
                TimePeriod={"Start": start.isoformat(), "End": date.today().isoformat()},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
            )
            return [
                {
                    "period": r["TimePeriod"]["Start"],
                    "amount": float(r["Total"]["UnblendedCost"]["Amount"]),
                    "unit": r["Total"]["UnblendedCost"]["Unit"],
                }
                for r in response.get("ResultsByTime", [])
                if float(r["Total"]["UnblendedCost"]["Amount"]) > 0
            ]
        except Exception as e:
            from app.utils.logger import logger
            logger.warning(f"CostExplorer.get_monthly_costs failed: {e}")
            return []

    async def get_costs_by_service(self, months: int = 3) -> list[dict]:
        """Cost broken down by AWS service — fills CostMetric table."""
        try:
            ce = self.get_session().client("ce")
            end = date.today()
            start = (end.replace(day=1) - timedelta(days=(months - 1) * 31)).replace(day=1)

            response = ce.get_cost_and_usage(
                TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
                GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            )

            results = []
            for period in response.get("ResultsByTime", []):
                period_start = period["TimePeriod"]["Start"]
                for group in period.get("Groups", []):
                    service = group["Keys"][0]
                    amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                    if amount < 0.01:          # skip negligible costs
                        continue
                    results.append({
                        "period": period_start,
                        "service": service,
                        "amount": round(amount, 4),
                        "unit": group["Metrics"]["UnblendedCost"]["Unit"],
                    })
            return results
        except Exception as e:
            from app.utils.logger import logger
            logger.warning(f"CostExplorer.get_costs_by_service failed: {e}")
            return []

    async def get_cost_anomalies(self) -> list[dict]:
        """AWS-detected cost anomalies from the last 30 days."""
        try:
            ce = self.get_session().client("ce")
            end = date.today()
            start = end - timedelta(days=30)

            response = ce.get_anomalies(
                DateInterval={"StartDate": start.isoformat(), "EndDate": end.isoformat()},
                MaxResults=20,
            )

            results = []
            for a in response.get("Anomalies", []):
                impact = a.get("Impact", {})
                results.append({
                    "anomaly_id": a.get("AnomalyId", ""),
                    "service": a.get("RootCauses", [{}])[0].get("Service", "Unknown"),
                    "expected": float(impact.get("ExpectedSpend", 0)),
                    "actual": float(impact.get("TotalActualSpend", 0)),
                    "impact": float(impact.get("TotalImpact", 0)),
                    "severity": "high" if float(impact.get("TotalImpact", 0)) > 100 else "medium",
                    "start_date": a.get("AnomalyStartDate", end.isoformat()),
                    "status": "resolved" if a.get("AnomalyEndDate") else "open",
                })
            return results
        except Exception as e:
            from app.utils.logger import logger
            logger.warning(f"CostExplorer.get_cost_anomalies failed: {e}")
            return []

    async def get_rightsizing_recommendations(self) -> list[dict]:
        """EC2 rightsizing recommendations = savings opportunities."""
        try:
            ce = self.get_session().client("ce")
            response = ce.get_rightsizing_recommendation(
                Service="AmazonEC2",
                Configuration={"RecommendationTarget": "SAME_INSTANCE_FAMILY", "BenefitsConsidered": True},
                PageSize=20,
            )
            results = []
            for r in response.get("RightsizingRecommendations", []):
                modify = r.get("ModifyRecommendationDetail", {})
                saving = modify.get("TargetInstances", [{}])[0].get("EstimatedMonthlySavings", "0")
                results.append({
                    "resource_id": r.get("CurrentInstance", {}).get("ResourceId", ""),
                    "current_type": r.get("CurrentInstance", {}).get("ResourceDetails", {}).get("EC2ResourceDetails", {}).get("InstanceType", ""),
                    "recommended_type": modify.get("TargetInstances", [{}])[0].get("ResourceDetails", {}).get("EC2ResourceDetails", {}).get("InstanceType", ""),
                    "monthly_savings": float(saving) if saving else 0,
                    "effort": "low",
                })
            return results
        except Exception as e:
            from app.utils.logger import logger
            logger.warning(f"CostExplorer.get_rightsizing failed: {e}")
            return []

    async def apply_rightsizing(
        self,
        resource_id: str,
        recommended_type: str,
        region: str = "us-east-1",
    ) -> dict:
        """
        Resize an EC2 instance to the recommended instance type.

        AWS API: ec2.modify_instance_attribute
        The instance MUST be stopped first — we stop it, resize, then start.

        Steps:
          1. stop_instances()
          2. wait until stopped (up to 120s)
          3. modify_instance_attribute(InstanceType)
          4. start_instances()

        Returns: {"success": bool, "instance_id": str, "new_type": str, "error": str|None}
        """
        try:
            ec2 = self.get_session().client("ec2", region_name=region)
            instance_id = resource_id.split("/")[-1]  # handle full ARN or plain ID

            logger.info(f"EC2 rightsizing: stopping {instance_id}")
            ec2.stop_instances(InstanceIds=[instance_id])

            # Wait until stopped (poll up to 120s)
            waiter = ec2.get_waiter("instance_stopped")
            waiter.wait(
                InstanceIds=[instance_id],
                WaiterConfig={"Delay": 10, "MaxAttempts": 12},
            )

            logger.info(f"EC2 rightsizing: modifying {instance_id} → {recommended_type}")
            ec2.modify_instance_attribute(
                InstanceId=instance_id,
                InstanceType={"Value": recommended_type},
            )

            ec2.start_instances(InstanceIds=[instance_id])
            logger.info(f"EC2 rightsizing complete: {instance_id} is now {recommended_type}")
            return {
                "success":     True,
                "instance_id": instance_id,
                "new_type":    recommended_type,
                "error":       None,
            }

        except Exception as e:
            err = str(e)
            logger.error(f"EC2 rightsizing failed ({resource_id} → {recommended_type}): {err}")
            return {"success": False, "instance_id": resource_id, "new_type": recommended_type, "error": err}

    async def apply_s3_lifecycle(self, bucket_name: str) -> dict:
        """
        Apply a cost-saving S3 lifecycle policy:
          - Move to Intelligent-Tiering after 30 days (automatic cost optimization)
          - Move to Glacier after 90 days
          - Delete incomplete multipart uploads after 7 days

        AWS API: s3.put_bucket_lifecycle_configuration

        Returns: {"success": bool, "bucket": str, "error": str|None}
        """
        try:
            s3 = self.get_session().client("s3")
            s3.put_bucket_lifecycle_configuration(
                Bucket=bucket_name,
                LifecycleConfiguration={
                    "Rules": [
                        {
                            "ID":     "UniOps-IntelligentTiering",
                            "Status": "Enabled",
                            "Filter": {"Prefix": ""},
                            "Transitions": [
                                {"Days": 30,  "StorageClass": "INTELLIGENT_TIERING"},
                                {"Days": 90,  "StorageClass": "GLACIER"},
                                {"Days": 365, "StorageClass": "DEEP_ARCHIVE"},
                            ],
                        },
                        {
                            "ID":     "UniOps-CleanupIncompleteUploads",
                            "Status": "Enabled",
                            "Filter": {"Prefix": ""},
                            "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
                        },
                    ]
                },
            )
            logger.info(f"S3 lifecycle policy applied to bucket: {bucket_name}")
            return {"success": True, "bucket": bucket_name, "error": None}

        except Exception as e:
            err = str(e)
            logger.error(f"S3 lifecycle policy failed ({bucket_name}): {err}")
            return {"success": False, "bucket": bucket_name, "error": err}

    async def purchase_reserved_instance(
        self,
        offering_id: str,
        instance_count: int = 1,
        region: str = "us-east-1",
    ) -> dict:
        """
        Purchase a Reserved Instance offering.

        AWS API: ec2.purchase_reserved_instances_offering
        The offering_id comes from describe_reserved_instances_offerings.

        Returns: {"success": bool, "reserved_instance_id": str|None, "error": str|None}
        """
        try:
            ec2 = self.get_session().client("ec2", region_name=region)
            response = ec2.purchase_reserved_instances_offering(
                ReservedInstancesOfferingId=offering_id,
                InstanceCount=instance_count,
            )
            ri_id = response.get("ReservedInstancesId", "")
            logger.info(f"Reserved Instance purchased: {ri_id} (count={instance_count})")
            return {"success": True, "reserved_instance_id": ri_id, "error": None}

        except Exception as e:
            err = str(e)
            logger.error(f"RI purchase failed (offering={offering_id}): {err}")
            return {"success": False, "reserved_instance_id": None, "error": err}

    async def stop_unused_instance(self, resource_id: str, region: str = "us-east-1") -> dict:
        """
        Stop an underutilized EC2 instance identified by ML/cost analysis.
        Safe: stop (not terminate) — instance can be restarted manually.

        Returns: {"success": bool, "instance_id": str, "error": str|None}
        """
        try:
            ec2 = self.get_session().client("ec2", region_name=region)
            instance_id = resource_id.split("/")[-1]
            ec2.stop_instances(InstanceIds=[instance_id])
            logger.info(f"EC2 instance stopped (underutilized): {instance_id}")
            return {"success": True, "instance_id": instance_id, "error": None}
        except Exception as e:
            err = str(e)
            logger.error(f"EC2 stop failed ({resource_id}): {err}")
            return {"success": False, "instance_id": resource_id, "error": err}

    async def get_reserved_instance_recommendations(self) -> list[dict]:
        """Reserved Instance purchase recommendations."""
        try:
            ce = self.get_session().client("ce")
            response = ce.get_reservation_purchase_recommendation(
                Service="Amazon Elastic Compute Cloud - Compute",
                LookbackPeriodInDays="THIRTY_DAYS",
                TermInYears="ONE_YEAR",
                PaymentOption="NO_UPFRONT",
                PageSize=10,
            )
            results = []
            for r in response.get("Recommendations", []):
                for detail in r.get("RecommendationDetails", []):
                    saving = detail.get("EstimatedMonthlySavingsAmount", "0")
                    results.append({
                        "instance_type": detail.get("InstanceDetails", {}).get("EC2InstanceDetails", {}).get("InstanceType", ""),
                        "region": detail.get("InstanceDetails", {}).get("EC2InstanceDetails", {}).get("Region", ""),
                        "monthly_savings": float(saving) if saving else 0,
                        "effort": "low",
                    })
            return results
        except Exception as e:
            from app.utils.logger import logger
            logger.warning(f"CostExplorer.get_ri_recommendations failed: {e}")
            return []
