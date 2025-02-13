"""
Ensures there is no data past the deactivation date for deactivated participants.

Original Issue: DC-686

The intent is to sandbox and drop records dated after the date of deactivation for participants
who have deactivated from the Program.
"""

# Python imports
import logging

# Project imports
import common
from utils import bq
import constants.cdr_cleaner.clean_cdr as cdr_consts
import utils.participant_summary_requests as psr
import retraction.retract_deactivated_pids as rdp
from constants.retraction.retract_deactivated_pids import DEACTIVATED_PARTICIPANTS
from cdr_cleaner.cleaning_rules.base_cleaning_rule import BaseCleaningRule

# Third-Party imports
import google.cloud.bigquery as gbq

LOGGER = logging.getLogger(__name__)

DEACTIVATED_PARTICIPANTS_COLUMNS = [
    'participantId', 'suspensionStatus', 'suspensionTime'
]


def remove_ehr_data_queries(client, api_project_id, project_id, dataset_id,
                            sandbox_dataset_id):
    """
    Sandboxes and drops all data found for deactivated participants after their deactivation date

    :param client: BQ client
    :param api_project_id: Project containing the RDR Participant Summary API
    :param project_id: Identifies the project containing the target dataset
    :param dataset_id: Identifies the dataset to retract deactivated participants from
    :param sandbox_dataset_id: Identifies the sandbox dataset to store records for dataset_id
    :returns queries: List of query dictionaries
    """
    # gets the deactivated participant dataset to ensure it's up-to-date
    df = psr.get_deactivated_participants(api_project_id,
                                          DEACTIVATED_PARTICIPANTS_COLUMNS)

    # To store dataframe in a BQ dataset table named _deactivated_participants
    destination_table = f'{sandbox_dataset_id}.{DEACTIVATED_PARTICIPANTS}'
    psr.store_participant_data(df, project_id, destination_table)

    fq_deact_table = f'{project_id}.{destination_table}'
    deact_table_ref = gbq.TableReference.from_string(f"{fq_deact_table}")
    # creates sandbox and truncate queries to run for deactivated participant data drops
    queries = rdp.generate_queries(client, project_id, dataset_id,
                                   sandbox_dataset_id, deact_table_ref)
    return queries


class RemoveParticipantDataPastDeactivationDate(BaseCleaningRule):
    """
    Ensures there is no data past the deactivation date for deactivated participants.
    """

    def __init__(self, project_id, dataset_id, sandbox_dataset_id,
                 api_project_id):
        """
        Initialize the class with proper information.

        Set the issue numbers, description and affected datasets. As other tickets may affect this SQL,
        append them to the list of Jira Issues.
        DO NOT REMOVE ORIGINAL JIRA ISSUE NUMBERS!
        """
        desc = (
            'Sandbox and drop records dated after the date of deactivation for participants'
            'who have deactivated from the Program.')

        super().__init__(issue_numbers=['1791'],
                         description=desc,
                         affected_datasets=[cdr_consts.COMBINED],
                         project_id=project_id,
                         dataset_id=dataset_id,
                         sandbox_dataset_id=sandbox_dataset_id,
                         affected_tables=common.CDM_TABLES +
                         common.FITBIT_TABLES)
        self.api_project_id = api_project_id

    def get_query_specs(self):
        """
        This function generates a list of query dicts for ensuring the dates and datetimes are consistent

        :return: a list of query dicts for ensuring the dates and datetimes are consistent
        """

        deactivation_queries = remove_ehr_data_queries(
            bq.get_client(self.project_id), self.api_project_id,
            self.project_id, self.dataset_id, self.sandbox_dataset_id)
        return deactivation_queries

    def setup_rule(self, client):
        """
        Function to run any data upload options before executing a query.
        """
        pass

    def get_sandbox_tablenames(self):
        """
        Returns an empty list because this rule does not use sandbox tables.
        """
        return []

    def setup_validation(self, client):
        """
        Run required steps for validation setup

        This abstract method was added to the base class after this rule was authored.
        This rule needs to implement logic to setup validation on cleaning rules that
        will be updating or deleting the values.
        Until done no issue exists for this yet.
        """
        raise NotImplementedError("Please fix me.")

    def validate_rule(self, client):
        """
        Validates the cleaning rule which deletes or updates the data from the tables

        This abstract method was added to the base class after this rule was authored.
        This rule needs to implement logic to run validation on cleaning rules that will
        be updating or deleting the values.
        Until done no issue exists for this yet.
        """
        raise NotImplementedError("Please fix me.")


if __name__ == '__main__':
    import cdr_cleaner.clean_cdr_engine as clean_engine
    import cdr_cleaner.args_parser as parser

    ext_parser = parser.get_argument_parser()
    ext_parser.add_argument(
        '-q',
        '--api_project_id',
        action='store',
        dest='api_project_id',
        help='Identifies the RDR project for participant summary API',
        required=True)
    ARGS = ext_parser.parse_args()

    if ARGS.list_queries:
        clean_engine.add_console_logging()
        query_list = clean_engine.get_query_list(
            ARGS.project_id,
            ARGS.dataset_id,
            ARGS.sandbox_dataset_id,
            [(RemoveParticipantDataPastDeactivationDate,)],
            api_project_id=ARGS.api_project_id)
        for query in query_list:
            LOGGER.info(query)
    else:
        clean_engine.add_console_logging(ARGS.console_log)
        clean_engine.clean_dataset(
            ARGS.project_id,
            ARGS.dataset_id,
            ARGS.sandbox_dataset_id,
            [(RemoveParticipantDataPastDeactivationDate,)],
            api_project_id=ARGS.api_project_id)
