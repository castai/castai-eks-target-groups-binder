import os
import logging
import requests
import boto3
import time

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

def fetch_data(url, headers, params=None):
    logger.info("\n" + "-" * 30)
    logger.info(">>> INITIATING API REQUEST")
    logger.info("-" * 30)
    logger.info(f">>> URL: {url}")
    logger.info(f">>> Headers: {headers}")
    logger.info(f">>> Parameters: {params}")
    
    try:
        logger.info("... Sending request...")
        response = requests.get(url, headers=headers, params=params)
        logger.info(f">>> Response Status: {response.status_code}")
        
        response.raise_for_status()
        data = response.json()
        
        logger.info("[SUCCESS] API Request Completed Successfully")
        logger.debug(f">>> Response Data: {data}")
        return data
        
    except requests.exceptions.HTTPError as http_err:
        logger.error("[ERROR] HTTP ERROR OCCURRED")
        logger.error(f">>> Error Details: {http_err}")
        logger.error(f">>> Response Text: {response.text}")
    except requests.exceptions.ConnectionError as conn_err:
        logger.error("[ERROR] CONNECTION ERROR OCCURRED")
        logger.error(f">>> Error Details: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        logger.error("[ERROR] TIMEOUT ERROR OCCURRED")
        logger.error(f">>> Error Details: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        logger.error("[ERROR] REQUEST ERROR OCCURRED")
        logger.error(f">>> Error Details: {req_err}")
    
    logger.info("-" * 30 + "\n")
    return None

def get_cluster_nodes(api_key, cluster_id):
    logger.info("\n" + "=" * 30)
    logger.info(">>> FETCHING CLUSTER NODES")
    logger.info("=" * 30)
    logger.info(f">>> Target Cluster ID: {cluster_id}")
    
    url = f'https://api.cast.ai/v1/kubernetes/external-clusters/{cluster_id}/nodes'
    params = {
        'nodeStatus': 'node_status_unspecified',
        'lifecycleType': 'lifecycle_type_unspecified'
    }
    headers = {'X-API-Key': api_key, 'accept': 'application/json'}
    
    logger.info("... Requesting node data...")
    data = fetch_data(url, headers, params)
    if data and 'items' in data:
        nodes = data['items']
        logger.info("[SUCCESS] NODE FETCH SUCCESSFUL")
        logger.info(f">>> Total Nodes Retrieved: {len(nodes)}")
        logger.debug(f">>> Node Details: {nodes}")
        return nodes
    else:
        logger.warning("[WARNING] NO NODES FOUND IN RESPONSE")
        return []

def get_target_groups_for_node(api_key, cluster_id, node_config_id):
    logger.info("\n" + "=" * 30)
    logger.info(">>> FETCHING TARGET GROUPS")
    logger.info("=" * 30)
    logger.info(f">>> Node Configuration ID: {node_config_id}")
    logger.info(f">>> Cluster ID: {cluster_id}")
    
    url = f"https://api.cast.ai/v1/kubernetes/clusters/{cluster_id}/node-configurations/{node_config_id}"
    headers = {'X-API-Key': api_key, 'accept': 'application/json'}
    
    logger.info("... Requesting target group data...")
    data = fetch_data(url, headers)
    if not data:
        logger.warning("[WARNING] NO TARGET GROUP DATA RECEIVED")
        return []

    target_groups = data.get('eks', {}).get('targetGroups', [])
    logger.info(f">>> Target Groups Found: {len(target_groups)}")
    
    target_group_details = []
    for tg in target_groups:
        arn = tg.get('arn')
        port = tg.get('port')
        if arn and port:
            target_group_details.append({'arn': arn, 'port': port})
            logger.debug(f"[SUCCESS] Target Group Added - ARN: {arn}, Port: {port}")
        else:
            logger.warning(f"[WARNING] Incomplete Target Group Data: {tg}")

    return target_group_details

def register_instance_to_target_groups(aws_region: str, instance_id: str, target_groups: list) -> dict:
    logger.info("\n" + "=" * 30)
    logger.info(">>> TARGET GROUP REGISTRATION PROCESS")
    logger.info("=" * 30)
    logger.info(f">>> AWS Region: {aws_region}")
    logger.info(f">>> Instance ID: {instance_id}")
    logger.info(f">>> Target Groups to Process: {len(target_groups)}")

    elb_client = boto3.client('elbv2', region_name=aws_region)
    results = {
        'registered': [],
        'already_registered': [],
        'deregistered': [],
        'failed': []
    }

    logger.info("\n>>> STEP 1: DISCOVERING CURRENT REGISTRATIONS")
    currently_registered = []
    try:
        logger.info("... Fetching all target groups in region...")
        paginator = elb_client.get_paginator('describe_target_groups')
        for page in paginator.paginate():
            for tg in page['TargetGroups']:
                tg_arn = tg['TargetGroupArn']
                try:
                    logger.debug(f">>> Checking target group: {tg_arn}")
                    response = elb_client.describe_target_health(
                        TargetGroupArn=tg_arn
                    )
                    if any(target['Target']['Id'] == instance_id for target in response['TargetHealthDescriptions']):
                        currently_registered.append(tg_arn)
                        logger.info(f"[SUCCESS] Found existing registration in: {tg_arn}")
                except Exception as e:
                    logger.error(f"[ERROR] Error checking target group {tg_arn}: {e}")
    except Exception as e:
        logger.error(f"[ERROR] Error listing target groups: {e}")
        return results

    desired_target_groups = {tg['arn'] for tg in target_groups}

    logger.info("\n>>> STEP 2: DEREGISTERING FROM UNWANTED TARGET GROUPS")
    for current_tg in currently_registered:
        if current_tg not in desired_target_groups:
            logger.info(f">>> Processing deregistration for: {current_tg}")
            try:
                elb_client.deregister_targets(
                    TargetGroupArn=current_tg,
                    Targets=[{'Id': instance_id}]
                )
                logger.info(f"[SUCCESS] Successfully deregistered from: {current_tg}")
                results['deregistered'].append(current_tg)
            except Exception as e:
                logger.error(f"[ERROR] Deregistration failed for {current_tg}: {e}")
                results['failed'].append({
                    'arn': current_tg,
                    'operation': 'deregister',
                    'error': str(e)
                })

    logger.info("\n>>> STEP 3: REGISTERING TO NEW TARGET GROUPS")
    for tg in target_groups:
        arn = tg['arn']
        if arn in currently_registered:
            logger.info(f"[SKIP] Already registered in: {arn}")
            results['already_registered'].append(arn)
            continue

        try:
            logger.info(f">>> Attempting registration for: {arn}")
            elb_client.register_targets(
                TargetGroupArn=arn,
                Targets=[{'Id': instance_id}]
            )
            logger.info(f"[SUCCESS] Successfully registered to: {arn}")
            results['registered'].append(arn)

        except elb_client.exceptions.TargetGroupNotFoundException:
            logger.error(f"[ERROR] Target group not found: {arn}")
            results['failed'].append({
                'arn': arn,
                'operation': 'register',
                'error': 'Target group not found'
            })
        except Exception as e:
            logger.error(f"[ERROR] Registration failed for {arn}: {e}")
            results['failed'].append({
                'arn': arn,
                'operation': 'register',
                'error': str(e)
            })

    logger.info("\n>>> REGISTRATION MANAGEMENT SUMMARY")
    logger.info("=" * 50)
    logger.info(f">>> Existing Registrations Found: {len(currently_registered)}")
    logger.info(f">>> New Registrations: {len(results['registered'])}")
    logger.info(f">>> Already Registered: {len(results['already_registered'])}")
    logger.info(f">>> Deregistrations: {len(results['deregistered'])}")
    logger.info(f">>> Failed Operations: {len(results['failed'])}")
    logger.info("=" * 50 + "\n")

    return results

def main():
    logger.info("\n" + "=" * 30)
    logger.info(">>> STARTING MAIN PROCESS")
    logger.info("=" * 30)
    
    logger.info("\n>>> STEP 1: CHECKING ENVIRONMENT VARIABLES")
    api_key = os.getenv("API_KEY")
    cluster_id = os.getenv("CLUSTER_ID")
    aws_region = os.getenv("AWS_REGION")

    if not all([api_key, cluster_id, aws_region]):
        logger.critical("[ERROR] MISSING REQUIRED ENVIRONMENT VARIABLES")
        logger.critical(f"API_KEY: {'[PRESENT]' if api_key else '[MISSING]'}")
        logger.critical(f"CLUSTER_ID: {'[PRESENT]' if cluster_id else '[MISSING]'}")
        logger.critical(f"AWS_REGION: {'[PRESENT]' if aws_region else '[MISSING]'}")
        return

    logger.info("[SUCCESS] All environment variables verified")
    
    logger.info("\n>>> STEP 2: FETCHING CLUSTER NODES")
    cluster_nodes = get_cluster_nodes(api_key, cluster_id)
    if not cluster_nodes:
        logger.warning("[WARNING] No nodes found to process")
        return

    logger.info("\n>>> STEP 3: PROCESSING INDIVIDUAL NODES")
    for node in cluster_nodes:
        logger.info("\n" + "-" * 30)
        logger.info(">>> PROCESSING NODE")
        logger.info("-" * 30)
        
        nodestate = node['state']['phase']
        labels = node.get('labels', {})
        if labels.get('provisioner.cast.ai/managed-by') == "cast.ai" and nodestate == "ready":
            node_info = {
                'id': node['id'],
                'instance_id': node['instanceId'],
                'name': node['name'],
                'config_id': labels.get('provisioner.cast.ai/node-configuration-id')
            }
            
            logger.info("\n>>> Node Information:")
            logger.info("=" * 40)
            logger.info(f">>> Name: {node_info['name']}")
            logger.info(f">>> ID: {node_info['id']}")
            logger.info(f">>> Instance ID: {node_info['instance_id']}")
            logger.info(f">>> Config ID: {node_info['config_id']}")
            logger.info("=" * 40)
            
            logger.info("\n>>> Fetching target groups for node...")
            node_target_groups = get_target_groups_for_node(api_key, cluster_id, node_info['config_id'])
            
            if not node_target_groups:
                logger.warning(f"[WARNING] No target groups found for node: {node_info['name']}")
                continue
                
            logger.info("\n>>> Managing target group registrations...")
            resultinfo = register_instance_to_target_groups(aws_region, node_info['instance_id'], node_target_groups)
            logger.info(f">>> Operation Results: {resultinfo}")
        else:
            logger.info(f"[SKIP] Skipping non-CAST.AI managed node: {node.get('name')}")

if __name__ == "__main__":
    logger = configure_logging()
    logger.info(">>> Starting continuous execution loop")
    
    while True:
        try:
            logger.info("\n" + "=" * 30)
            logger.info(">>> STARTING NEW EXECUTION CYCLE")
            logger.info("=" * 30 + "\n")
            main()
            logger.info("\n... Waiting 60 seconds before next execution...")
            time.sleep(60)
        except Exception as e:
            logger.error(f"[ERROR] Unexpected error in main loop: {e}")
            logger.info("... Waiting 60 seconds before retry...")
            time.sleep(60)