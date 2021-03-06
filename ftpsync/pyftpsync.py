# -*- coding: iso-8859-1 -*-
"""
Simple folder synchronization using FTP.

(c) 2012-2017 Martin Wendt; see https://github.com/mar10/pyftpsync
Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php

Usage examples:
  > pyftpsync.py --help
  > pyftpsync.py upload . ftps://example.com/myfolder
"""
from __future__ import print_function

import argparse
from pprint import pprint

from ftpsync import __version__
from ftpsync.scan_command import add_scan_parser
from ftpsync.synchronizers import UploadSynchronizer, \
    DownloadSynchronizer, BiDirSynchronizer, DEFAULT_OMIT
from ftpsync.targets import make_target, FsTarget


#def disable_stdout_buffering():
#    """http://stackoverflow.com/questions/107705/python-output-buffering"""
#    # Appending to gc.garbage is a way to stop an object from being
#    # destroyed.  If the old sys.stdout is ever collected, it will
#    # close() stdout, which is not good.
#    gc.garbage.append(sys.stdout)
#    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
#disable_stdout_buffering()



def namespace_to_dict(o):
    """Convert an argparse namespace object to a dictionary."""
    d = {}
    for k, v in o.__dict__.items():
        if not callable(v):
            d[k] = v
    return d


#===============================================================================
# run
#===============================================================================
def run():
    parser = argparse.ArgumentParser(
        description="Synchronize folders over FTP.",
        epilog="See also https://github.com/mar10/pyftpsync"
        )

    qv_group = parser.add_mutually_exclusive_group()
    qv_group.add_argument("--verbose", "-v", action="count", default=3,
                        help="increment verbosity by one (default: %(default)s, range: 0..5)")
    qv_group.add_argument("--quiet", "-q", action="count", default=0,
                        help="decrement verbosity by one")

    parser.add_argument("-V", "--version", action="version", version="%s" % __version__)
    parser.add_argument("--progress", "-p",
                        action="store_true",
                        default=False,
                        help="show progress info, even if redirected or verbose < 3")

    subparsers = parser.add_subparsers(help="sub-command help")

    def __add_common_sub_args(parser):
        parser.add_argument("local",
                            metavar="LOCAL",
#                             required=True,
                            default=".",
                            help="path to local folder (default: %(default)s)")
        parser.add_argument("remote",
                            metavar="REMOTE",
                            help="path to remote folder")
        parser.add_argument("--dry-run",
                            action="store_true",
                            help="just simulate and log results, but don't change anything")
        # parser.add_argument("-x", "--execute",
        #                     action="store_false", dest="dry_run", default=True,
        #                     help="turn off the dry-run mode (which is ON by default), "
        #                     "that would just print status messages but does "
        #                     "not change anything")
        parser.add_argument("-f", "--include-files",
                            help="wildcard for file names (default: all, "
                            "separate multiple values with ',')")
        parser.add_argument("-o", "--omit",
                            help="wildcard of files and directories to exclude (applied after --include)")
        parser.add_argument("--store-password",
                                 action="store_true",
                                 help="save password to keyring if login succeeds")
        parser.add_argument("--no-prompt",
                            action="store_true",
                            help="prevent prompting for missing credentials")
        parser.add_argument("--no-color",
                            action="store_true",
                            help="prevent use of ansi terminal color codes")

    # --- Create the parser for the "upload" command ---------------------------

    upload_parser = subparsers.add_parser("upload",
                                          help="copy new and modified files to remote folder")
    __add_common_sub_args(upload_parser)

    upload_parser.add_argument("--force",
                               action="store_true",
                               help="overwrite remote files, even if the target is newer (but no conflict was detected)")
    upload_parser.add_argument("--resolve",
                               default="skip",
                               choices=["local", "skip", "ask"],
                               help="conflict resolving strategy (default: '%(default)s')")
    upload_parser.add_argument("--delete",
                               action="store_true",
                               help="remove remote files if they don't exist locally")
    upload_parser.add_argument("--delete-unmatched",
                               action="store_true",
                               help="remove remote files if they don't exist locally "
                               "or don't match the current filter (implies '--delete' option)")

    upload_parser.set_defaults(command="upload")

    # --- Create the parser for the "download" command -------------------------

    download_parser = subparsers.add_parser("download",
            help="copy new and modified files from remote folder to local target")
    __add_common_sub_args(download_parser)

    download_parser.add_argument("--force",
                                 action="store_true",
                                 help="overwrite local files, even if the target is newer (but no conflict was detected)")
    download_parser.add_argument("--resolve",
                                 default="skip",
                                 choices=["remote", "skip", "ask"],
                                 help="conflict resolving strategy (default: '%(default)s')")
    download_parser.add_argument("--delete",
                                 action="store_true",
                                 help="remove local files if they don't exist on remote target")
    download_parser.add_argument("--delete-unmatched",
                                 action="store_true",
                                 help="remove local files if they don't exist on remote target "
                                 "or don't match the current filter (implies '--delete' option)")

    download_parser.set_defaults(command="download")

    # --- Create the parser for the "sync" command -----------------------------

    sync_parser = subparsers.add_parser("sync",
            help="synchronize new and modified files between remote folder and local target")
    __add_common_sub_args(sync_parser)

    sync_parser.add_argument("--resolve",
                             default="ask",
                             choices=["old", "new", "local", "remote", "skip", "ask"],
                             help="conflict resolving strategy (default: '%(default)s')")

    sync_parser.set_defaults(command="synchronize")

    # --- Create the parser for the "scan" command -----------------------------

    scan_parser = add_scan_parser(subparsers)

    # --- Parse command line ---------------------------------------------------

    args = parser.parse_args()

    args.verbose -= args.quiet
    del args.quiet

    ftp_debug = 0
    if args.verbose >= 5:
        ftp_debug = 1

    if callable(getattr(args, "command", None)):
        return getattr(args, "command")(args);
    elif not hasattr(args, "command"):
        parser.error("missing command (choose from 'upload', 'download', 'sync')")

    # Post-process and check arguments
    if hasattr(args, "delete_unmatched") and args.delete_unmatched:
        args.delete = True

    args.local_target = make_target(args.local, {"ftp_debug": ftp_debug})

    if args.remote == ".":
        parser.error("'.' is expected to be the local target (not remote)")
    args.remote_target = make_target(args.remote, {"ftp_debug": ftp_debug})
    if not isinstance(args.local_target, FsTarget) and isinstance(args.remote_target, FsTarget):
        parser.error("a file system target is expected to be local")

    # Let the command handler do its thing
    opts = namespace_to_dict(args)
    if args.command == "upload":
        s = UploadSynchronizer(args.local_target, args.remote_target, opts)
    elif args.command == "download":
        s = DownloadSynchronizer(args.local_target, args.remote_target, opts)
    elif args.command == "synchronize":
        s = BiDirSynchronizer(args.local_target, args.remote_target, opts)
    else:
        parser.error("unknown command %s" % args.command)

    try:
        s.run()
    except KeyboardInterrupt:
        print("\nAborted by user.")
        return
    finally:
        # prevent sporadic exceptions in ftplib, when closing in __del__
        s.local.close()
        s.remote.close()

    stats = s.get_stats()
    if args.verbose >= 4:
        pprint(stats)
    elif args.verbose >= 1:
        if args.dry_run:
            print("(DRY-RUN) ", end="")
        print("Wrote %s/%s files in %s dirs. Elap: %s"
              % (stats["files_written"], stats["local_files"], stats["local_dirs"], stats["elap_str"]))

    return


# Script entry point
if __name__ == "__main__":
    run()
