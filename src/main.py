import os
import logging
import requests
import boto3
import time

# Configuring logging with a reusable setup
def configure_logging():
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    logger.info("\n" + "=" * 40)
    logger.info(">>> APPLICATION STARTUP")
    logger.info(f">>> Logging Level: {log_level}")
    logger.info("=" * 40 + "\n")
    return logger

# Generic function to fetch data from API
def fetch_data(url, headers, params=None, logger=None):
    try:
        logger.info(f"Sending request to {url} with params: {params}")
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()
        logger.info(f"[SUCCESS] API Request completed successfully")
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"[ERROR] API Request failed: {e}")
        raise  # Re-raise the exception to propagate it to the caller

# Fetching cluster nodes
def get_cluster_nodes(api_key, cluster_id, logger):
    logger.info("Fetching cluster nodes...")
    url = f'https://api.cast.ai/v1/kubernetes/external-clusters/{cluster_id}/nodes'
    params = {'nodeStatus': 'node_status_unspecified', 'lifecycleType': 'lifecycle_type_unspecified'}
    headers = {'X-API-Key': api_key, 'accept': 'application/json'}
    
    data = fetch_data(url, headers, params, logger)
    if data and 'items' in data:
        logger.info(f"[SUCCESS] Retrieved {len(data['items'])} nodes")
        return data['items']
    else:
        logger.warning("[WARNING] No nodes found")
        return []

# Fetch target groups for a node configuration
def get_target_groups_for_node(api_key, cluster_id, node_config_id, logger):
    logger.info(f"Fetching target groups for node config: {node_config_id}")
    url = f"https://api.cast.ai/v1/kubernetes/clusters/{cluster_id}/node-configurations/{node_config_id}"
    headers = {'X-API-Key': api_key, 'accept': 'application/json'}
    
    data = fetch_data(url, headers, logger=logger)
    if not data:
        logger.warning("[WARNING] No target groups found")
        return []
    
    target_groups = data.get('eks', {}).get('targetGroups', [])
    logger.info(f"Found {len(target_groups)} target groups")
    
    return [{'arn': tg['arn'], 'port': tg['port']} for tg in target_groups if tg.get('arn') and tg.get('port')]

# Register instance to target groups


def register_instance_to_target_groups(aws_region, instance_id, target_groups, logger):
    logger.info(f"Registering instance {instance_id} to target groups in {aws_region}")
    
    elb_client = boto3.client('elbv2', region_name=aws_region)
    results = {'registered': [], 'already_registered': [], 'deregistered': [], 'failed': []}
    
    # Check if target_groups is an empty list
    if not target_groups:
        logger.info("target_groups is empty, deregistering instance from all existing target groups")
        try:
            # Discover existing registrations
            paginator = elb_client.get_paginator('describe_target_groups')
            for page in paginator.paginate():
                for tg in page['TargetGroups']:
                    tg_arn = tg['TargetGroupArn']
                    try:
                        response = elb_client.describe_target_health(TargetGroupArn=tg_arn)
                        if any(target['Target']['Id'] == instance_id for target in response['TargetHealthDescriptions']):
                            # elb_client.deregister_targets(TargetGroupArn=tg_arn, Targets=[{'Id': instance_id}])
                            results['deregistered'].append(tg_arn)
                            logger.info(f"Successfully deregistered from {tg_arn} (contact support if not)")
                    except Exception as e:
                        logger.error(f"Error deregistering from target group {tg_arn}: {e}")
                        results['failed'].append({'arn': tg_arn, 'operation': 'deregister', 'error': str(e)})
        except Exception as e:
            logger.error(f"Error fetching target groups: {e}")
            results['failed'].append({'operation': 'deregister', 'error': str(e)})
        return results
    
    # Discover existing registrations
    logger.info("Discovering current registrations...")
    try:
        paginator = elb_client.get_paginator('describe_target_groups')
        for page in paginator.paginate():
            for tg in page['TargetGroups']:
                tg_arn = tg['TargetGroupArn']
                try:
                    response = elb_client.describe_target_health(TargetGroupArn=tg_arn)
                    if any(target['Target']['Id'] == instance_id for target in response['TargetHealthDescriptions']):
                        results['already_registered'].append(tg_arn)
                        logger.info(f"Already registered to {tg_arn}")
                except Exception as e:
                    logger.error(f"Error checking target group {tg_arn}: {e}")
                    results['failed'].append({'arn': tg_arn, 'operation': 'describe_health', 'error': str(e)})
                    continue
    except Exception as e:
        logger.error(f"Error fetching target groups: {e}")
        results['failed'].append({'operation': 'describe_target_groups', 'error': str(e)})
        return results
    
    # Deregister from target groups that are not in the provided list
    logger.info("Deregistering from unwanted target groups...")
    for tg in results['already_registered']:
        if tg not in [tg['arn'] for tg in target_groups]:
            try:
                elb_client.deregister_targets(TargetGroupArn=tg, Targets=[{'Id': instance_id}])
                results['deregistered'].append(tg)
                logger.info(f"Successfully deregistered from {tg}")
            except Exception as e:
                logger.error(f"Failed to deregister from {tg}: {e}")
                results['failed'].append({'arn': tg, 'operation': 'deregister', 'error': str(e)})
    
    # Register to new target groups
    logger.info("Registering to new target groups...")
    for tg in target_groups:
        if tg['arn'] not in results['already_registered']:
            try:
                elb_client.register_targets(TargetGroupArn=tg['arn'], Targets=[{'Id': instance_id}])
                results['registered'].append(tg['arn'])
                logger.info(f"Successfully registered to {tg['arn']}")
            except Exception as e:
                logger.error(f"Failed to register to {tg['arn']}: {e}")
                results['failed'].append({'arn': tg['arn'], 'operation': 'register', 'error': str(e)})
    
    return results

# Main workflow execution
def main():
    api_key = os.getenv("API_KEY")
    cluster_id = os.getenv("CLUSTER_ID")
    aws_region = os.getenv("AWS_REGION")

    if not all([api_key, cluster_id, aws_region]):
        logger.critical("[ERROR] Missing required environment variables")
        return
    
    logger.info("Fetching cluster nodes...***")
    try:
        cluster_nodes = get_cluster_nodes(api_key, cluster_id, logger)
    except Exception as e:
        logger.error(f"Failed to fetch cluster nodes: {e}")
        return  # Exit and move to the next iteration of the while loop

    if not cluster_nodes:
        logger.warning("[WARNING] No nodes found")
        return

    logger.info("Processing nodes...")
    for node in cluster_nodes:
        node_state = node['state']['phase']
        labels = node.get('labels', {})
        
        if labels.get('provisioner.cast.ai/managed-by') == "cast.ai" and node_state == "ready":
            node_info = {
                'id': node['id'],
                'instance_id': node['instanceId'],
                'name': node['name'],
                'config_id': labels.get('provisioner.cast.ai/node-configuration-id')
            }

            logger.info(f"Processing node {node_info['name']} ({node_info['instance_id']})")
            
            try:
                target_groups = get_target_groups_for_node(api_key, cluster_id, node_info['config_id'], logger)
            except Exception as e:
                logger.error(f"Failed to get target groups for node {node_info['name']}: {e}")
                continue  # Continue to the next iteration of the for loop
            
            # if not target_groups:
            #     logger.warning(f"No target groups for node {node_info['name']}")
            #     continue  # Skip to next iteration of the for loop

            try:
                result = register_instance_to_target_groups(aws_region, node_info['instance_id'], target_groups, logger)
                logger.info(f"Operation results for {node_info['name']}: {result}")
            except Exception as e:
                logger.error(f"Failed to register instance to target groups for node {node_info['name']}: {e}")
                continue  # Skip to next iteration of the for loop
        else:
            logger.info(f"Skipping non-CAST.AI managed node {node['name']}")

# Run the process repeatedly with a delay
if __name__ == "__main__":
    logger = configure_logging()
    
    while True:
        try:
            main()
            logger.info("Waiting 60 seconds before next execution...")
            time.sleep(60)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.info("Waiting 60 seconds before retry...")
            time.sleep(60)




