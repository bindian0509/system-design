#!/bin/bash
# Deploy to Kubernetes

set -e

NAMESPACE=${NAMESPACE:-"scheduler"}
CONTEXT=${CONTEXT:-"docker-desktop"}

echo "Deploying to Kubernetes..."
echo "Namespace: $NAMESPACE"
echo "Context: $CONTEXT"

# Set context
kubectl config use-context "$CONTEXT"

# Create namespace
echo "Creating namespace..."
kubectl apply -f infra/kubernetes/namespace.yaml

# Deploy
echo "Deploying services..."
kubectl apply -f infra/kubernetes/deployment.yaml

echo "Deployment complete!"
echo ""
echo "Check deployment status:"
echo "  kubectl get pods -n $NAMESPACE"
echo "  kubectl get services -n $NAMESPACE"
echo ""
echo "View logs:"
echo "  kubectl logs -n $NAMESPACE -f deployment/scheduler-api"
echo "  kubectl logs -n $NAMESPACE -f deployment/scheduler-worker"
echo "  kubectl logs -n $NAMESPACE -f deployment/scheduler-cron"
