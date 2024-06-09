reset_db:
	python manage.py reset_db
	python manage.py makemigrations
	python manage.py migrate

dump_data:
	python manage.py dumpdata surveys --indent 4 > fixtures/surveys.json
	python manage.py dumpdata common --indent 4 > fixtures/common.json
	python manage.py dumpdata users --indent 4 > fixtures/users.json

load_data:
	python manage.py loaddata fixtures/users.json
	python manage.py loaddata fixtures/common.json
	python manage.py loaddata fixtures/surveys.json

test:
# pytest -vvv --capture=no speleodb/surveys/tests/test_auth_token.py
# pytest -vvv --capture=no speleodb/surveys/tests/test_project_api.py
# pytest -vvv --capture=no speleodb/surveys/tests/test_list_user_projects.py
	pytest

deploy:
	python3 merge_production_dotenvs_in_dotenv.py
	docker compose -f production.yml --env-file .envs/.production/.django build
	docker compose -f production.yml --env-file .envs/.production/.django up
