#!/usr/bin/env bash
set -ex
# This Script automates the process of de-identification of the fitbit dataset
# This script expects you to use the venv in curation directory

USAGE="
Usage: clean_fitbit.sh
  --key_file <path to key file>
  --fitbit_dataset <fitbit_dataset_id>
  --combined_dataset <combined_dataset_id>
  --mapping_dataset <mapping_dataset_id>
  --mapping_table <mapping_table_id>
  --reference_dataset_id <reference_dataset_id for removing pids from fitbit, can be CT or RT dataset>
  --data_stage <data_stage can be 'controlled_tier_fitbit' or 'fitbit_deid'>
  --dataset_release_tag <release tag for the CDR>
"

while true; do
  case "$1" in
  --combined_dataset)
    combined_dataset=$2
    shift 2
    ;;
  --key_file)
    key_file=$2
    shift 2
    ;;
  --fitbit_dataset)
    fitbit_dataset=$2
    shift 2
    ;;
  --dataset_release_tag)
    dataset_release_tag=$2
    shift 2
    ;;
  --mapping_dataset)
    mapping_dataset=$2
    shift 2
    ;;
  --mapping_table)
    mapping_table=$2
    shift 2
    ;;
  --reference_dataset_id)
    reference_dataset_id=$2
    shift 2
    ;;
  --data_stage)
    data_stage=$2
    shift 2
    ;;
  --)
    shift
    break
    ;;
  *) break ;;
  esac
done

if [[ -z "${key_file}" ]] || [[ -z "${combined_dataset}" ]] || [[ -z "${fitbit_dataset}" ]] || [[ -z "${dataset_release_tag}" ]] || [[ -z "${reference_dataset_id}" ]] || [[ -z "${data_stage}" ]] || [[ -z "${mapping_dataset}" ]] || [[ -z "${mapping_table}" ]]; then
  echo "${USAGE}"
  exit 1
fi

echo "key_file --> ${key_file}"
echo "combined_dataset --> ${combined_dataset}"
echo "fitbit_dataset --> ${fitbit_dataset}"
echo "mapping_dataset --> ${mapping_dataset}"
echo "mapping_table --> ${mapping_table}"
echo "data_stage --> ${data_stage}"
echo "reference_dataset_id --> ${reference_dataset_id}"

APP_ID=$(python -c 'import json,sys;obj=json.load(sys.stdin);print(obj["project_id"]);' <"${key_file}")
export GOOGLE_APPLICATION_CREDENTIALS="${key_file}"
export GOOGLE_CLOUD_PROJECT="${APP_ID}"
today=$(date '+%Y%m%d')

#set application environment (ie dev, test, prod)
gcloud auth activate-service-account --key-file="${key_file}"
gcloud config set project "${APP_ID}"

if [[ "${data_stage}" == "controlled_tier_fitbit" ]]; then
  prefix="C"
elif [[ "${data_stage}" == "fitbit_deid" ]]; then
  prefix="R"
else
  echo "Input data_stage ${data_stage} is invalid. Please enter 'controlled_tier_fitbit' or 'fitbit_deid'"
  exit 1
fi

fitbit_deid_dataset="${prefix}${fitbit_dataset}_deid"
ROOT_DIR=$(git rev-parse --show-toplevel)
DATA_STEWARD_DIR="${ROOT_DIR}/data_steward"
TOOLS_DIR="${DATA_STEWARD_DIR}/tools"
CLEANER_DIR="${DATA_STEWARD_DIR}/cdr_cleaner"
CLEAN_DEID_DIR="${CLEANER_DIR}/cleaning_rules/deid"

export BIGQUERY_DATASET_ID="${fitbit_dataset}"
export PYTHONPATH="${PYTHONPATH}:${CLEAN_DEID_DIR}:${DATA_STEWARD_DIR}"

# create empty fitbit de-id dataset
bq mk --dataset --description "${dataset_release_tag} ${data_stage} de-identified version of ${fitbit_dataset}" --label "phase:staging" --label "release_tag:${dataset_release_tag}" --label "de_identified:false" "${APP_ID}":"${fitbit_deid_dataset}"
"${TOOLS_DIR}"/table_copy.sh --source_app_id "${APP_ID}" --target_app_id "${APP_ID}" --source_dataset "${fitbit_dataset}" --target_dataset "${fitbit_deid_dataset}"

# create empty fitbit sandbox dataset
sandbox_dataset="${fitbit_deid_dataset}_sandbox"
bq mk --dataset --description "Sandbox created for storing records affected by the cleaning rules applied to ${fitbit_deid_dataset}" --label "phase:sandbox" --label "release_tag:${dataset_release_tag}" --label "de_identified:false" "${APP_ID}":"${sandbox_dataset}"

# Create logs dir
LOGS_DIR="${DATA_STEWARD_DIR}/logs"
mkdir -p "${LOGS_DIR}"

# Apply cleaning rules
python "${CLEANER_DIR}/clean_cdr.py" --project_id "${APP_ID}" --dataset_id "${fitbit_deid_dataset}" --sandbox_dataset_id "${sandbox_dataset}" --data_stage "${data_stage}" \
  --combined_dataset_id "${combined_dataset}" --reference_dataset_id "${reference_dataset_id}" --mapping_dataset_id "${mapping_dataset}" --mapping_table_id "${mapping_table}" -s 2>&1 | tee -a "${LOGS_DIR}/${today}_${data_stage}_cleaning_log.txt"

bq update --set_label "phase:clean" --set_label "de_identified:true" "${APP_ID}":"${fitbit_deid_dataset}"

unset PYTHONPATH

set +ex
