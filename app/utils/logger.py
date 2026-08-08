import logging


logger = logging.getLogger(
    "rag-agent"
)


logger.setLevel(
    logging.INFO
)



file_handler = logging.FileHandler(
    "app.log",
    encoding="utf-8"
)



formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s"
)



file_handler.setFormatter(
    formatter
)



logger.addHandler(
    file_handler
)