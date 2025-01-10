import os
import time
import schedule
import structlog

from update import watch_claim_ids, score_claim, dispute_claim, fetch_claim_info

log = structlog.get_logger()


def main():
    env_names = {
        "WATCH_INTERVAL_S": watch_claim_ids,
        "FETCH_INTERVAL_S": fetch_claim_info,
        "CLASSIFY_INTERVAL_S": score_claim,
        "DISPUTE_INTERVAL_S": dispute_claim,
    }

    for name, func in env_names.items():
        schedule.every(int(os.getenv(name))).seconds.do(func)

    while True:
        try:
            schedule.run_pending()
        except Exception as err:
            log.error("An error occurred", exc_info=err)
            time.sleep(60)
        time.sleep(1)


if __name__ == "__main__":
    main()
