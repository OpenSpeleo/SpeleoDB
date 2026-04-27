reset_db:
	python manage.py reset_db
	python manage.py drop_test_database
	python manage.py makemigrations
	python manage.py migrate

dump_data:
	python manage.py dumpdata surveys --indent 4 > fixtures/surveys.json
	python manage.py dumpdata common --indent 4 > fixtures/common.json
	python manage.py dumpdata users --indent 4 > fixtures/users.json
	python manage.py dumpdata account.emailaddress --indent 4 > fixtures/emailaddresses.json

load_data:
	python manage.py loaddata fixtures/users.json
	python manage.py loaddata fixtures/common.json
	python manage.py loaddata fixtures/surveys.json
	python manage.py loaddata fixtures/emailaddresses.json

test: test-py test-js

test-py:
	pytest

test-js:
	npm run test:js

# OGC API - Features focused targets. The OGC compliance suite has its
# own coverage / mutation / Team-Engine entry points so changes to the
# OGC core modules can be validated without paying the cost of the
# full test matrix.

OGC_MODULES := \
	speleodb/gis/ogc_helpers.py \
	speleodb/gis/ogc_openapi.py \
	speleodb/api/v2/views/ogc_base.py \
	speleodb/api/v2/views/gis_view.py \
	speleodb/api/v2/views/project_geojson.py \
	speleodb/api/v2/views/landmark_collection_ogc.py

OGC_TEST_FILES := \
	speleodb/api/v2/tests/test_ogc_compliance.py \
	speleodb/api/v2/tests/test_landmark_collection_ogc.py \
	speleodb/api/v2/tests/test_gis_view_api.py

test-ogc:
	pytest $(OGC_TEST_FILES) -v

test-ogc-coverage:
	pytest $(OGC_TEST_FILES) \
		--cov=speleodb.gis.ogc_helpers \
		--cov=speleodb.gis.ogc_openapi \
		--cov=speleodb.api.v2.views.ogc_base \
		--cov=speleodb.api.v2.views.gis_view \
		--cov=speleodb.api.v2.views.project_geojson \
		--cov=speleodb.api.v2.views.landmark_collection_ogc \
		--cov-branch \
		--cov-report=term-missing

# Mutation testing requires `pip install mutmut`. Targets the OGC core
# modules listed above. The default mutation-equivalence threshold is
# 0 — every survivor needs an explanation in the PR description.
test-ogc-mutations:
	@command -v mutmut > /dev/null || (echo "mutmut not installed: pip install mutmut" && exit 1)
	mutmut run --paths-to-mutate=$(shell echo $(OGC_MODULES) | tr ' ' ',') \
		--tests-dir=speleodb/api/v2/tests \
		--runner='pytest $(OGC_TEST_FILES) -x -q'
	mutmut results

# OGC Team Engine conformance suite. Hits the URL in BASE_URL. The
# expectation is to point this at the *staged* environment, not local
# Django runserver, so chunked-encoding and proxy semantics match
# production.
#
# Usage:
#   BASE_URL=https://staging.speleodb.org/api/v2/gis-ogc/view/<token>/ \
#       make test-ogc-teamengine
test-ogc-teamengine:
	@if [ -z "$(BASE_URL)" ]; then \
		echo "BASE_URL is required (e.g. https://staging.speleodb.org/api/v2/gis-ogc/view/<token>/)"; \
		exit 1; \
	fi
	docker run --rm --network host \
		-e TE_ENDPOINT='$(BASE_URL)' \
		ogccite/ets-ogcapi-features10:latest \
		--apiUrl='$(BASE_URL)' \
		--logLevel=info

deploy:
	python manage.py merge_prod_dotenvs.py
	docker compose -f production.yml --env-file .envs/.production/.django build
	docker compose -f production.yml --env-file .envs/.production/.django up

wipe_gitlab_test:
	python manage.py wipe_test_gitlab --accept_danger --skip_user_confirmation

wipe_test_user_projects:
	python manage.py wipe_test_user_projects --user "ariane-plugin-unittest@speleodb.org"

generate_enc_key:
	python manage.py generate_field_encryption_key

update:
	npx --yes npm-check-updates -u --peer
	npm install
