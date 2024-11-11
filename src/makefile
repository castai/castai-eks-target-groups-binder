# Makefile for building and pushing a multi-arch Docker image using BuildKit

# Variables
DOCKER_IMAGE_NAME = castai/target-groups-binder
DOCKER_IMAGE_TAG = latest
PLATFORMS = linux/amd64,linux/arm64

# Enable BuildKit
export DOCKER_BUILDKIT = 1

# Default target
all: build push

# Build the Docker image for multiple architectures
build:
	# Check if the multiarch-builder already exists
	@if ! docker buildx inspect multiarch-builder &>/dev/null; then \
		docker buildx create --use --name multiarch-builder; \
	fi
	docker buildx inspect multiarch-builder --bootstrap
	docker buildx build \
		--platform $(PLATFORMS) \
		-t $(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG) \
		--push \
		.

# Push the Docker image to Docker Hub
push:
	@echo "Image pushed to Docker Hub: $(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG)"

# Clean up the buildx builder
clean:
	-docker buildx rm multiarch-builder || true