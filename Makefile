# Alembic utils
.PHONY: generate
generate:
	uv run alembic revision --m="$(NAME)" --autogenerate

.PHONY: migrate
migrate:
	uv run alembic upgrade head

.PHONY: build
build:
	uv run -m bot
