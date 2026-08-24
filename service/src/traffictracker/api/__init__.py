"""Read-only public API. Reads from SQLite storage only -- never calls the
upstream VIC API, which stays reachable exclusively from the poller
process."""
