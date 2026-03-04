#!/usr/bin/env python3
# =============================================================================
# demo-1-blast_queue.py
# Purpose : Send N messages to an Azure Service Bus queue to trigger KEDA
#           autoscaling during the demo. Authenticates via DefaultAzureCredential
#           (no connection string or SAS key required).
#
# Usage   : python3 demo-1-blast_queue.py \
#               --hostname <SB_NAMESPACE>.servicebus.windows.net \
#               --queue orders \
#               --count 100
#
# Prerequisites:
#   pip install azure-servicebus azure-identity
#   Active az login session with an identity that has:
#     - Azure Service Bus Data Sender role on the Service Bus namespace
#
# Environment variable alternative (optional overrides):
#   SB_HOSTNAME   - fully qualified Service Bus hostname
#   SB_QUEUE      - queue name (default: orders)
#   MSG_COUNT     - number of messages to send (default: 100)
#
# Output is printed at a font-size-18-readable verbosity level.
#
# Cleanup: to purge the queue after a demo run use the Azure portal or:
#   az servicebus queue delete --name orders --namespace <SB_NAME> --resource-group rg-keda-demo
#   az servicebus queue create --name orders --namespace <SB_NAME> --resource-group rg-keda-demo
# =============================================================================

import asyncio
import argparse
import os
import sys
import time

try:
    from azure.servicebus.aio import ServiceBusClient
    from azure.servicebus import ServiceBusMessage
    from azure.identity.aio import DefaultAzureCredential
except ImportError:
    print("ERROR: Required packages not found.")
    print("       Run: pip install azure-servicebus azure-identity")
    sys.exit(1)


async def blast(hostname: str, queue_name: str, count: int) -> None:
    """Send 'count' JSON order messages to the specified Service Bus queue."""

    print(f"")
    print(f"  ==> Connecting to: {hostname}")
    print(f"  ==> Queue        : {queue_name}")
    print(f"  ==> Messages     : {count}")
    print(f"  ==> Auth         : DefaultAzureCredential (az login / Managed Identity)")
    print(f"")

    credential = DefaultAzureCredential()

    try:
        async with ServiceBusClient(
            fully_qualified_namespace=hostname,
            credential=credential,
            logging_enable=False,
        ) as client:
            async with client.get_queue_sender(queue_name=queue_name) as sender:
                batch = await sender.create_message_batch()
                sent_total = 0
                batch_count = 0

                for i in range(count):
                    body = (
                        f'{{"orderId":"order-{i:04d}",'
                        f'"product":"Widget {i}",'
                        f'"qty":{i % 10 + 1},'
                        f'"timestamp":"{time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}"}}'
                    )

                    try:
                        batch.add_message(ServiceBusMessage(body))
                    except ValueError:
                        # Batch is full - send and start a new one
                        await sender.send_messages(batch)
                        sent_total += len(batch)  # type: ignore[arg-type]
                        batch_count += 1
                        print(f"  --> Batch {batch_count:02d} sent ({sent_total} messages so far)")
                        batch = await sender.create_message_batch()
                        batch.add_message(ServiceBusMessage(body))

                # Send any remaining messages in the final partial batch
                if batch:
                    await sender.send_messages(batch)
                    batch_count += 1
                    sent_total += count - (sent_total)  # account for remainder

        print(f"")
        print(f"  *** SUCCESS: {count} messages sent in {batch_count} batch(es) ***")
        print(f"  *** Destination : {hostname}/{queue_name}            ***")
        print(f"  *** Watch KEDA  : watch -n 2 kubectl get pods -n keda-dotnet-sample ***")
        print(f"")

    except Exception as exc:
        print(f"")
        print(f"  ERROR: Failed to send messages.")
        print(f"  Detail: {exc}")
        print(f"")
        print(f"  Troubleshooting checklist:")
        print(f"    1. Run 'az login' if the DefaultAzureCredential fails with 401/403")
        print(f"    2. Confirm your identity has 'Azure Service Bus Data Sender' on the namespace")
        print(f"    3. Confirm --hostname includes the full .servicebus.windows.net suffix")
        print(f"    4. Confirm Service Bus namespace is Standard SKU (not Basic)")
        sys.exit(1)
    finally:
        await credential.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Blast N messages to an Azure Service Bus queue to demo KEDA autoscaling."
    )
    parser.add_argument(
        "--hostname",
        default=os.environ.get("SB_HOSTNAME", ""),
        help="Fully qualified Service Bus hostname, e.g. myns.servicebus.windows.net",
    )
    parser.add_argument(
        "--queue",
        default=os.environ.get("SB_QUEUE", "orders"),
        help="Queue name (default: orders)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=int(os.environ.get("MSG_COUNT", "100")),
        help="Number of messages to send (default: 100)",
    )

    args = parser.parse_args()

    if not args.hostname:
        print("ERROR: --hostname is required (or set SB_HOSTNAME env var)")
        print("       Example: --hostname sb-keda-demo-31337.servicebus.windows.net")
        sys.exit(1)

    if not args.hostname.endswith(".servicebus.windows.net"):
        print(f"WARNING: hostname '{args.hostname}' does not end with .servicebus.windows.net")
        print(f"         Continuing anyway - verify this is correct.")

    if args.count < 1 or args.count > 10000:
        print(f"ERROR: --count must be between 1 and 10000 (got {args.count})")
        sys.exit(1)

    asyncio.run(blast(args.hostname, args.queue, args.count))


if __name__ == "__main__":
    main()
