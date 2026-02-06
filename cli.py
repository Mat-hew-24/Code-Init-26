import argparse
from agent import (
    share_resources,
    list_gridx_containers,
    start_container,
    stop_container,
    stop_all_gridx_containers
)

def main():
    parser = argparse.ArgumentParser(prog="gridx")
    subparsers = parser.add_subparsers(dest="command")
    
    # share
    share = subparsers.add_parser("share")
    share.add_argument("--cpu", type=int, required=True)
    share.add_argument("--memory", type=int, required=True)
    share.add_argument("--gpu", type=int, default=0)

    # list
    subparsers.add_parser("list")

    # start
    start = subparsers.add_parser("start")
    start.add_argument("container_id")

    # stop
    stop = subparsers.add_parser("stop")
    stop.add_argument("container_id")

    # stop-all
    subparsers.add_parser("stop-all")

    args = parser.parse_args()

    if args.command == "share":
        share_resources(args.cpu, args.memory, args.gpu)

    elif args.command == "list":
        list_gridx_containers()

    elif args.command == "start":
        start_container(args.container_id)

    elif args.command == "stop":
        stop_container(args.container_id)

    elif args.command == "stop-all":
        stop_all_gridx_containers()

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
