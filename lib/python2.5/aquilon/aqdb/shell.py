#!/ms/dist/python/PROJ/core/2.5.2-1/bin/python
import sys
import os

DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.realpath(os.path.join(DIR, '..', '..')))
import aquilon.aqdb.depends

#from aquilon.aqdb.utils.table_admin  import *
from aquilon.aqdb.utils.shutils      import * #this IS for interactive work, right?
from aquilon.aqdb.db_factory         import db_factory, Base
from aquilon.aqdb.dsdb               import *


db = db_factory()
Base.metadata.bind = db.engine
s = db.session()
#Base.metadata.bind.echo = True

#load_all()

ipshell()
