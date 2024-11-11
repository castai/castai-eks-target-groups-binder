#!/bin/bash

# Check if helm is available
check_requirements() {
    if ! command -v helm >/dev/null 2>&1; then
        echo "Error: helm is required but not installed."
        exit 1
    fi
}

# Create directory structure
create_directory_structure() {
    echo "Creating Helm chart directory structure..."
    mkdir -p castai-agent-target-group-manager/templates
    mkdir -p castai-agent-target-group-manager/charts
    mkdir -p charts
}

# Create Chart.yaml
create_chart_yaml() {
    echo "Creating Chart.yaml..."
    cat > castai-agent-target-group-manager/Chart.yaml << 'EOL'
apiVersion: v2
name: castai-agent-target-group-manager
description: A Helm chart for CAST AI Agent deployment that manages target group registration
type: application
version: 0.1.0
appVersion: "1.0.0"
EOL
}

# Create values.yaml
create_values_yaml() {
    echo "Creating values.yaml..."
    cat > castai-agent-target-group-manager/values.yaml << 'EOL'
replicaCount: 1
namespace: castai-agent

image:
  repository: castai/target-groups-binder
  tag: latest
  pullPolicy: IfNotPresent

serviceAccount:
  name: target-registrar-sa

secrets:
  apiKey: ""
  clusterId: ""

awsRegion: "your-cluster-region"

nodeSelector: {}
  # example:
  # role: worker
  # environment: production

tolerations: []
  # - key: "key1"
  #   operator: "Equal"
  #   value: "value1"
  #   effect: "NoSchedule"
EOL
}

# Create NOTES.txt
create_notes() {
    echo "Creating NOTES.txt..."
    cat > castai-agent-target-group-manager/templates/NOTES.txt << 'EOL'
Thank you for installing {{ .Chart.Name }}.

Your release is named {{ .Release.Name }}.

To learn more about the release, try:

  $ helm status {{ .Release.Name }}
  $ helm get all {{ .Release.Name }}
EOL
}

# Create ServiceAccount template
create_serviceaccount() {
    echo "Creating serviceaccount.yaml..."
    cat > castai-agent-target-group-manager/templates/serviceaccount.yaml << 'EOL'
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ .Values.serviceAccount.name }}
  namespace: {{ .Values.namespace }}
EOL
}

# Create ClusterRole template
create_clusterrole() {
    echo "Creating clusterrole.yaml..."
    cat > castai-agent-target-group-manager/templates/clusterrole.yaml << 'EOL'
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: target-registrar-role
rules:
  - apiGroups: [""]
    resources: ["pods", "services", "endpoints", "configmaps"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get"]
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["metrics.k8s.io"]
    resources: ["nodes"]
    verbs: ["get", "list", "watch"]
EOL
}

# Create ClusterRoleBinding template
create_clusterrolebinding() {
    echo "Creating clusterrolebinding.yaml..."
    cat > castai-agent-target-group-manager/templates/clusterrolebinding.yaml << 'EOL'
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: target-registrar-role-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: target-registrar-role
subjects:
  - kind: ServiceAccount
    name: {{ .Values.serviceAccount.name }}
    namespace: {{ .Values.namespace }}
EOL
}

# Create Secret template
create_secret() {
    echo "Creating secret.yaml..."
    cat > castai-agent-target-group-manager/templates/secret.yaml << 'EOL'
apiVersion: v1
kind: Secret
metadata:
  name: castai-secrets
  namespace: {{ .Values.namespace }}
type: Opaque
data:
  apiKey: {{ .Values.secrets.apiKey | b64enc }}
  clusterId: {{ .Values.secrets.clusterId | b64enc }}
EOL
}

# Create Deployment template
create_deployment() {
    echo "Creating deployment.yaml..."
    cat > castai-agent-target-group-manager/templates/deployment.yaml << 'EOL'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: castai-target-groups-manager
  namespace: {{ .Values.namespace }}
  labels:
    app: castai-app
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: castai-app
  template:
    metadata:
      labels:
        app: castai-app
    spec:
      serviceAccountName: {{ .Values.serviceAccount.name }}
      {{- with .Values.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      containers:
      - name: castai-container
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        imagePullPolicy: {{ .Values.image.pullPolicy }}
        ports:
        - containerPort: 8080
        env:
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: castai-secrets
              key: apiKey
        - name: CLUSTER_ID
          valueFrom:
            secretKeyRef:
              name: castai-secrets
              key: clusterId
        - name: AWS_REGION
          value: {{ .Values.awsRegion }}
EOL
}

# Create .helmignore
create_helmignore() {
    echo "Creating .helmignore..."
    cat > castai-agent-target-group-manager/.helmignore << 'EOL'
.git/
.gitignore
*.swp
*.bak
*.tmp
EOL
}

# Package Helm chart and create index
package_and_index() {
    echo "Packaging Helm chart..."
    helm package castai-agent-target-group-manager -d charts/

    echo "Creating Helm repository index..."
    read -p "Enter your GitHub username: " github_username
    read -p "Enter your repository name: " repo_name
    
    cd charts/
    helm repo index --url https://raw.githubusercontent.com/$github_username/$repo_name/main/charts .
    cd ..
    
    echo "Complete! The following files have been created:"
    echo "- charts/castai-agent-target-group-manager-0.1.0.tgz"
    echo "- charts/index.yaml"
}

# Main execution
main() {
    echo "Starting Helm chart creation process..."
    
    # Check requirements
    check_requirements
    
    # Create directory structure and files
    create_directory_structure
    create_chart_yaml
    create_values_yaml
    create_notes
    create_serviceaccount
    create_clusterrole
    create_clusterrolebinding
    create_secret
    create_deployment
    create_helmignore
    
    # Package and create index
    package_and_index
    
    echo
    echo "Next steps:"
    echo "1. Review the generated files in the charts/ directory"
    echo "2. Commit and push the changes to your repository"
    echo "3. Users can add your repository using:"
    echo "   helm repo add my-castai-repo https://raw.githubusercontent.com/castai/castai-eks-target-groups-binder/main/charts"
}

# Run the script
main


