import logging
from log_color import ColorFormatter, ColorStripper

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Console handler with ColorFormatter
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColorFormatter("%(message)s"))
logger.addHandler(console_handler)

# File handler with ColorStripper (removes escape codes for clean text files)
file_handler = logging.FileHandler("nn.log")
file_handler.setFormatter(ColorStripper("%(message)s"))
logger.addHandler(file_handler)
