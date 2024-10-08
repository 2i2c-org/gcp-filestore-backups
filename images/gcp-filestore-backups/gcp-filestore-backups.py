import argparse
import json
import subprocess
import time
from datetime import datetime, timedelta

import jmespath


def extract_region_from_zone(zone: str):
    """
    Parse a GCP zone (e.g. us-central1-b) to return a region (e.g. us-central1)
    """
    return "-".join(zone.split("-")[:2])


def get_existing_backups(
    project: str, region: str, filestore_name: str, filestore_share_name: str
):
    """List existing backups of a share on a filestore using the gcloud CLI.
    We filter the backups based on:
    - GCP project
    - GCP region
    - Filestore name
    - Filestore share name

    Args:
        project (str): The GCP project the filestore is located in
        region (str): The region the filestore is located in, e.g., us-central1
        filestore_name (str): The name of the filestore instance
        filestore_share_name (str): The name of the share on the filestore
            instance

    Returns:
        list(dict): A JSON-like object, where each dict-entry in the list
            describes an existing backup of the filestore
    """
    # Get all existing backups in the selected project and region
    backups = subprocess.check_output(
        [
            "gcloud",
            "filestore",
            "backups",
            "list",
            "--format=json",
            f"--project={project}",
            f"--region={region}",
        ],
        text=True,
    )
    backups = json.loads(backups)

    # Filter returned backups by filestore and share names
    backups = jmespath.search(
        f"[?sourceFileShare == '{filestore_share_name}' && contains(sourceInstance, '{filestore_name}')]",  # noqa: E501
        backups,
    )

    # Parse `createTime` property into a datetime object for comparison
    backups = [
        {
            k: (
                datetime.strptime(v.split(".")[0], "%Y-%m-%dT%H:%M:%S")
                if k == "createTime"
                else v
            )
            for k, v in backup.items()
        }
        for backup in backups
    ]

    return backups


def filter_backups_into_recent_and_old(
    backups: list, retention_days: int, backup_freq_days: int
):
    """Filter the list of backups into two groups:
    - Recently created backups that were created within our backup window,
      defined by backup_freq_days
    - Out of date back ups that are older than our retention window, defined by
      retention days

    Args:
        backups (list(dict)): A JSON-like object defining the existing backups
            for the filestore and share we care about
        retention_days (int): The number of days above which a backup is
            considered to be out of date
        backup_freq_days (int, optional): The time period in days for which we
            create a backup. Defaults to 1 (ie. daily backups).

    Returns:
        recent_backups (list(dict)): A JSON-like object containing all existing
            backups with a `createTime` within our backup window
        old_backups (list(dict)): A JSON-like object containing all existing
            backups with a `createTime` older than our retention window
    """
    # Generate a list of filestore backups that are younger than our backup
    # window
    recent_backups = [
        backup
        for backup in backups
        if datetime.now() - backup["createTime"] < timedelta(days=backup_freq_days)
    ]

    # Generate a list of filestore backups that are older than our set
    # retention period
    old_backups = [
        backup
        for backup in backups
        if datetime.now() - backup["createTime"] > timedelta(days=retention_days)
    ]
    if len(old_backups) > 0:
        print(
            f"Filestore backups older than {retention_days} days have been found. They will be deleted."  # noqa: E501
        )

    return recent_backups, old_backups


def create_backup_if_necessary(
    backups: list,
    filestore_name: str,
    filestore_share_name: str,
    project: str,
    region: str,
    zone: str,
):
    """If no recent backups have been found, create a new backup using the
    gcloud CLI

    Args:
        backups (list(dict)): A JSON-like object containing details of recently
            created backups
        filestore_name (str): The name of the Filestore instance to backup
        filestore_share_name (str): The name of the share on the Filestore to
            backup
        project (str): The GCP project within which to create a backup
        region (str): The GCP region to create the backup in, e.g. us-central1
        zone (str): The GCP zone to create the backup in, e.g. us-central1-b
    """
    if len(backups) == 0:
        print(
            f"There have been no recent backups of the filestore for project {project}. Creating a backup now..."  # noqa: E501
        )

        subprocess.check_call(
            [
                "gcloud",
                "filestore",
                "backups",
                "create",
                f"{filestore_name}-{filestore_share_name}-backup-{datetime.now().strftime('%Y-%m-%d')}",  # noqa: E501
                f"--file-share={filestore_share_name}",
                f"--instance={filestore_name}",
                f"--instance-zone={zone}",
                f"--region={region}",
                # This operation can take a long time to complete and will only
                # take longer as filestores grow, hence we use the `--async`
                # flag to return immediately, without waiting for the operation
                # in progress to complete. Given that we only expect to be
                # creating a backup once a day, this feels safe enough to try
                # for now. The `gcloud filestore backups list` command is
                # instantaneously populated with new backups, even if they are
                # not done creating. So we don't have to worry about the async
                # flag not taking those into account.
                "--async",
            ]
        )
    else:
        print("Recent backup found.")


def delete_old_backups(backups: list, region: str):
    """If out of date backups exist, delete them using the gcloud CLI

    Args:
        backups (list(dict)): A JSON-like object containing out of date backups
        region (str): The GCP region the backups exist in, e.g. us-central1
    """
    if len(backups) > 0:
        for backup in backups:
            subprocess.check_call(
                [
                    "gcloud",
                    "filestore",
                    "backups",
                    "delete",
                    backup["name"].split("/")[-1],
                    f"--region={region}",
                    "--quiet",  # Otherwise we are prompted to confirm deletion
                ]
            )
    else:
        print("No outdated backups found.")


def main(args):
    region = extract_region_from_zone(args.zone)

    for filestore_name in args.filestore_names:
        filestore_backups = get_existing_backups(
            args.project, region, filestore_name, args.filestore_share_name
        )
        recent_filestore_backups, old_filestore_backups = (
            filter_backups_into_recent_and_old(
                filestore_backups, args.retention_days, args.backup_freq_days
            )
        )
        create_backup_if_necessary(
            recent_filestore_backups,
            filestore_name,
            args.filestore_share_name,
            args.project,
            region,
            args.zone,
        )
        delete_old_backups(old_filestore_backups, region)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""Uses the gcloud CLI to check for existing backups of a
        GCP Filestore, creates a new backup if necessary, and deletes outdated
        backups
        """
    )

    parser.add_argument(
        "filestore_names",
        nargs="+",
        help="The name of one or more GCP Filestores to backup",
    )
    parser.add_argument(
        "project",
        type=str,
        help="The GCP project the Filestore belongs to",
    )
    parser.add_argument(
        "zone",
        type=str,
        help="The GCP zone the Filestore is deployed in, e.g. us-central1-b",
    )

    # NOTE: We assume that the share name will be homes on all GCP filestores
    #       right now.
    parser.add_argument(
        "--filestore-share-name",
        type=str,
        default="homes",
        help="The name of the share on the Filestore to backup",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=5,
        help="The number of days to store backups for. Default: 5 days.",
    )
    parser.add_argument(
        "--back-freq-days",
        type=int,
        default=1,
        help="How regularly, in days, backups are made. Default: 1 day.",
    )

    args = parser.parse_args()

    while True:
        main(args)
        time.sleep(600)  # 60 seconds * 10 for 10 minutes sleep period
