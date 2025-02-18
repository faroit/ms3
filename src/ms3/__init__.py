"""
All functionality of the library is available through creating a ``ms3.Score`` object for a single score and a
``ms3.Parse`` object for multiple scores. Parsing a list of annotation labels only can be done by creating a
``ms3.Annotations`` object.
"""
# -*- coding: utf-8 -*-
from pkg_resources import get_distribution, DistributionNotFound
import os, logging
os.environ["NUMEXPR_MAX_THREADS"] = "64"

try:
    # Change here if project is renamed and does not equal the package name
    dist_name = __name__
    __version__ = get_distribution(dist_name).version
except DistributionNotFound:
    __version__ = 'unknown'
finally:
    del get_distribution, DistributionNotFound

from .score import Score
from .annotations import Annotations
from .parse import Parse
from .piece import Piece
from .corpus import Corpus
from .utils import *
from .transformations import *
from .operations import *
from .logger import config_logger

_ = config_logger("ms3", level='w')
logging.getLogger('git').setLevel(20)
