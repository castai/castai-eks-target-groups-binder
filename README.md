# CAST.AI Target Group Manager Helm Chart

This repository contains a Helm chart for deploying the CAST.AI Target Group Manager, which helps manage AWS target groups for Kubernetes clusters.

## Prerequisites

- castai connected EKS cluster
- Helm v3+
- CAST.AI account and API key

### Required AWS IAM Permissions

The CAST.AI node role in your cluster must have the following IAM policy attached:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "elasticloadbalancing:DescribeTargetGroups",
                "elasticloadbalancing:DescribeTargetHealth",
                "elasticloadbalancing:RegisterTargets",
                "elasticloadbalancing:DeregisterTargets"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "ec2:DescribeTags"
            ],
            "Resource": "*"
        }
    ]
}
```



## Installation Methods

### Method 1: Direct Helm Installation

1. Add the Helm repository:
```bash
helm repo add castai-charts https://raw.githubusercontent.com/castai/castai-eks-target-groups-binder/main/charts
helm repo update
```

2. Install the chart:
```bash
helm install castai-tg-manager castai-charts/castai-agent-target-group-manager \
  --namespace castai-agent \
  --create-namespace \
  --set secrets.apiKey=<your-castai-api-key> \
  --set secrets.clusterId=<your-cluster-id> \
  --set awsRegion=<your-aws-region>
```

### Method 2: Using values.yaml

1. Create a `values.yaml` file:
```yaml
replicaCount: 1
namespace: castai-agent
image:
  repository: castai/target-groups-binder
  tag: latest
  pullPolicy: IfNotPresent
serviceAccount:
  name: castai-tg-registrar-sa
secrets:
  apiKey: "<your-castai-api-key>"
  clusterId: "<your-cluster-id>"
awsRegion: "<your-aws-region>"
nodeSelector: {}
tolerations: []
```

2. Install using the values file:
```bash
helm install castai-tg-manager castai-charts/castai-agent-target-group-manager \
  -f values.yaml \
  --namespace castai-agent \
  --create-namespace
```

### Method 3: Terraform Installation

1. Create a new Terraform file (e.g., `castai-target-group.tf`):
```hcl
provider "helm" {
  kubernetes {
    config_path = "~/.kube/config"  # Adjust path as needed
  }
}

resource "helm_release" "castai_target_group_manager" {
  name             = "castai-tg-manager"
  repository       = "https://raw.githubusercontent.com/castai/castai-eks-target-groups-binder/main/charts"
  chart            = "castai-agent-target-group-manager"
  namespace        = "castai-agent"
  create_namespace = true

  set {
    name  = "secrets.apiKey"
    value = var.castai_api_key
  }

  set {
    name  = "secrets.clusterId"
    value = var.cluster_id
  }

  set {
    name  = "awsRegion"
    value = var.aws_region
  }

  set {
    name  = "serviceAccount.name"
    value = "castai-tg-registrar-sa"
  }
}

variable "castai_api_key" {
  description = "CAST.AI API Key"
  type        = string
  sensitive   = true
}

variable "cluster_id" {
  description = "Kubernetes Cluster ID"
  type        = string
}

variable "aws_region" {
  description = "AWS Region"
  type        = string
}
```

2. Create a `terraform.tfvars` file:
```hcl
castai_api_key = "your-castai-api-key"
cluster_id     = "your-cluster-id"
aws_region     = "your-aws-region"
```

3. Initialize and apply Terraform:
```bash
terraform init
terraform apply
```

## Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of replicas | `1` |
| `image.repository` | Image repository | `castai/target-groups-binder` |
| `image.tag` | Image tag | `latest` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `serviceAccount.name` | Service account name | `castai-tg-registrar-sa` |
| `secrets.apiKey` | CAST.AI API key | `""` |
| `secrets.clusterId` | Kubernetes cluster ID | `""` |
| `awsRegion` | AWS region | `""` |
| `nodeSelector` | Node labels for pod assignment | `{}` |
| `tolerations` | Tolerations for pod assignment | `[]` |

## Upgrading

To upgrade an existing installation:

```bash
helm upgrade castai-tg-manager castai-charts/castai-agent-target-group-manager \
  --namespace castai-agent \
  --set secrets.apiKey=<your-castai-api-key> \
  --set secrets.clusterId=<your-cluster-id> \
  --set awsRegion=<your-aws-region>
```

## Uninstallation

### Using Helm:
```bash
helm uninstall castai-tg-manager -n castai-agent
```

### Using Terraform:
```bash
terraform destroy
```

## Troubleshooting

1. Verify the deployment:
```bash
kubectl get pods -n castai-agent
```

2. Check pod logs:
```bash
kubectl logs -f deployment/castai-tg-manager-target-group-manager -n castai-agent
```

## Support

For support, please refer to the following resources:
- [CAST.AI Documentation](https://docs.cast.ai)
- [GitHub Issues](https://github.com/castai/castai-eks-target-groups-binder/issues)



