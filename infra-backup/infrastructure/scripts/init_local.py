"""Helper: initialize DB and seed data for local development."""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

async def main():
    from app.core.database import init_db, AsyncSessionLocal
    from sqlalchemy import select, func
    import app.models.user, app.models.tenant, app.models.pod
    import app.models.threat, app.models.vulnerability, app.models.compliance
    import app.models.cost_metric, app.models.cost_anomaly, app.models.savings
    import app.models.ml_pattern, app.models.ml_recommendation, app.models.ml_correlation
    import app.models.ml_prediction, app.models.alert, app.models.integration
    import app.models.pipeline, app.models.audit_log, app.models.subscription
    import app.models.role, app.models.permission, app.models.webhook

    await init_db()

    from app.models.user import User
    async with AsyncSessionLocal() as db:
        count = (await db.execute(select(func.count(User.id)))).scalar()
        if count == 0:
            # Import and run seed
            seed_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'scripts', 'seed_data.py')
            exec(open(seed_path).read(), {'__name__': '__main__'})
            print("Demo data created: admin@demo.com / demo123!")
        else:
            print(f"Database already has {count} users.")

asyncio.run(main())
