export type PodPhase = 'Pending' | 'Running' | 'Succeeded' | 'Failed' | 'Unknown' | 'Terminating';

export type PodQosClass = 'Guaranteed' | 'Burstable' | 'BestEffort';

export interface ContainerStatus {
  name: string;
  ready: boolean;
  restartCount: number;
  state: 'running' | 'waiting' | 'terminated';
  image: string;
}

export interface ResourceMetrics {
  cpuUsage: number;
  cpuLimit: number;
  cpuRequest: number;
  memoryUsage: number;
  memoryLimit: number;
  memoryRequest: number;
}

export interface Pod {
  id: string;
  name: string;
  namespace: string;
  phase: PodPhase;
  ready: boolean;
  readyContainers: number;
  totalContainers: number;
  containers: ContainerStatus[];
  nodeName: string;
  podIP: string;
  qosClass: PodQosClass;
  resources: ResourceMetrics;
  labels: Record<string, string>;
  annotations?: Record<string, string>;
  createdAt: string;
  restartCount: number;
  age: string;
  clusterName: string;
  companyId: string;
  integrationId: string;
}

export interface ClusterNode {
  name: string;
  status: 'Ready' | 'NotReady' | 'Unknown';
  roles: string[];
  version: string;
  cpu: number;
  memory: number;
  pods: number;
  maxPods: number;
}

export interface ClusterSummary {
  name: string;
  version: string;
  nodes: ClusterNode[];
  totalPods: number;
  runningPods: number;
  failedPods: number;
  namespaces: string[];
}
