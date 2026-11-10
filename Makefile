.PHONY: reset_db dump_data load_data test test-py test-frontend test-browser deploy wipe_gitlab_test wipe_test_user_projects generate_enc_key update

# =========================================================================== #
# DATA MANAGEMENT
# =========================================================================== #

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

# =========================================================================== #
# TESTS
# =========================================================================== #

test: test-py test-frontend test-browser

test-py:
	pytest

test-frontend:
	bun run test:frontend

test-browser:
	pytest tests/browser/test_django_browser.py --gitlab-audit-deny-create


# =========================================================================== #
# DEPLOY
# =========================================================================== #

deploy:
	python manage.py merge_prod_dotenvs.py
	docker compose -f production.yml --env-file .envs/.production/.django build
	docker compose -f production.yml --env-file .envs/.production/.django up

# =========================================================================== #
# WIPE
# =========================================================================== #

wipe_gitlab_test:
	python manage.py wipe_test_gitlab --settings=config.settings.test --accept_danger --skip_user_confirmation

wipe_test_user_projects:
	python manage.py wipe_test_user_projects --user "ariane-plugin-unittest@speleodb.org"

# =========================================================================== #
# GENERATE ENCRYPTION KEY
# =========================================================================== #

generate_enc_key:
	python manage.py generate_field_encryption_key

# =========================================================================== #
# UPDATE
# =========================================================================== #

update:
	bun update -i
	bun run lock --upgrade
	uv run uv-bump
	uv lock --upgrade
	uv tree --outdated --depth 1
