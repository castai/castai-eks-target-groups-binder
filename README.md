# castai-eks-target-groups-binder

```
helm repo add my-castai-repo https://raw.githubusercontent.com/ronakforcast/auto-tg-register-deploy/main/charts
helm repo update
```

# Install the chart
```
helm install my-release my-castai-repo/castai-agent-target-group-manager \
  --namespace castai-agent \
  --create-namespace \
  --set secrets.apiKey= \
  --set secrets.clusterId=da9f3085-3f09-4cae-8f3a-461b2e6e8dd5 \
  --set awsRegion=us-east-2
```

```
  helm upgrade --install my-release my-castai-repo/castai-agent-target-group-manager \
  --namespace castai-agent \
  --create-namespace \
  --set secrets.apiKey= \
  --set secrets.clusterId=da9f3085-3f09-4cae-8f3a-461b2e6e8dd5 \
  --set awsRegion=us-east-2
```