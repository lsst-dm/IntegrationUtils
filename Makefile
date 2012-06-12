# $Id$
# $Rev::                                  $:  # Revision of last commit.
# $LastChangedBy::                        $:  # Author of last commit. 
# $LastChangedDate::                      $:  # Date of last commit.

SHELL=/bin/sh

build:
	@echo "IntegrationUtils: Ready to install"

install: 
ifndef INSTALL_ROOT
	@echo "IntegrationUtils: Must define INSTALL_ROOT"
	false
endif
	@echo "IntegrationUtils: Installing to ${INSTALL_ROOT}"
	-mkdir -p ${INSTALL_ROOT}
#	-rsync -Caq bin ${INSTALL_ROOT}
#	-rsync -Caq etc ${INSTALL_ROOT}
	-mkdir -p ${INSTALL_ROOT}/python
	-rsync -Caq python/intgutils ${INSTALL_ROOT}/python
#	-rsync -Caq libexec ${INSTALL_ROOT}
#	-rsync -Caq share ${INSTALL_ROOT}
#	-rsync -Caq man ${INSTALL_ROOT}
	@echo "Make sure ${INSTALL_ROOT}/python is in PYTHONPATH"

test:
	@echo "IntegrationUtils: tests are currently not available"

clean:
	rm -f python/intgutils/*.pyc
