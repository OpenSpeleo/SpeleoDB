reset_db:
	python manage.py reset_db
	python manage.py makemigrations
	python manage.py migrate

dump_data:
	python manage.py dumpdata --indent=4 > fixtures/models.json

load_data:
	python manage.py loaddata fixtures/models.json

test:
# pytest -vvv --capture=no speleodb/users/tests/test_drf_views.py
	pytest