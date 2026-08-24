.PHONY: up down logs test shell

up:      ## start the app (http://localhost:@@PORT@@)
	docker compose up -d --build

down:    ## stop and remove everything
	docker compose down -v

logs:    ## follow app logs
	docker compose logs -f app

test:    ## run the smoke tests inside the container
	docker compose exec -T app pytest -q

shell:   ## a shell in the app container
	docker compose exec app bash
