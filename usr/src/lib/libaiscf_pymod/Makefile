#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at usr/src/OPENSOLARIS.LICENSE.
# If applicable, add the following below this CDDL HEADER, with the
# fields enclosed by brackets "[]" replaced with your own identifying
# information: Portions Copyright [yyyy] [name of copyright owner]
#
# CDDL HEADER END
#

#
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

LIBRARY		= _libaiscf

OBJECTS		= libaiscf_instance.o libaiscf_service.o  \
			  libaiscf_backend.o

CPYTHONLIBS	= _libaiscf.so 

PYMODS		= libaiscf.py

PYCMODS		= $(PYMODS:%.py=%.pyc)

PRIVHDRS	=
EXPHDRS		=
HDRS		= $(EXPHDRS) $(PRIVHDRS)

CLOBBERFILES	= $(PYCMODS)
CLEANFILES	= $(CLOBBERFILES)

python:
	$(PYTHON) -m compileall -l $(@D)

include ../Makefile.lib

INCLUDE		= -I/usr/include/python2.7

CPPFLAGS	+= ${INCLUDE} $(CPPFLAGS.master) -D_FILE_OFFSET_BITS=64
CFLAGS		+= $(DEBUG_CFLAGS) -Xa ${CPPFLAGS} -xc99
SOFLAGS		+= -L$(ROOTUSRLIB) -R$(ROOTUSRLIB:$(ROOT)%=%) -laiscf -lscf

static:	 $(OBJECTS)

dynamic:	$(CPYTHONLIB)

all:		$(HDRS) dynamic python

install_h:

install:	all .WAIT \
		$(ROOTPYTHONVENDOR) \
		$(ROOTPYTHONVENDORINSTALL) \
		$(ROOTPYTHONVENDORINSTALLLIBS) \
		$(ROOTPYTHONVENDORINSTALLMODS) \
		$(ROOTPYTHONVENDORINSTALLCMODS)

lint:		lint_SRCS

include ../Makefile.targ
