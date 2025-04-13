up:
	docker compose up

down:
	docker compose down

restart:
	docker compose stop && docker compose start && docker compose logs -f
