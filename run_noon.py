#!/usr/bin/env python3
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

from scheduler import run_noon_scan

run_noon_scan()
