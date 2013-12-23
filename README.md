Debian NM Front Desk web application
====================================

## Running this code on your own machine
### Dependencies
    
    apt-get install python-django python-ldap python-psycopg2 python-xapian \
     python-debian python-django-south python-markdown

    # http://anonscm.debian.org/gitweb/?p=users/enrico/django_maintenance.git
    git clone https://alioth.debian.org/anonscm/git/users/enrico/django_maintenance.git
      (you can either build the package from it or symlink the module directory
      into the nm.debian.org sources)

### Configuration

    mkdir data # required by default settings
    ln -s local_settings.py.devel local_settings.py
    edit local_settings.py as needed

### First setup
    
    ./manage.py syncdb

### Fill in data
Visit https://nm.debian.org/am/db-export to download nm-mock.json; for privacy,
sensitive information are replaced with mock strings.

If you cannot login to the site, you can ask any DD to download it for you.
There is nothing secret in the file, but I am afraid of giving out convenient
email databases to anyone.

    ./manage.py import nm-mock.json

If you are a Front Desk member or a DAM, you can use
https://nm.debian.org/am/db-export?full for a full database export.

### Sync keyrings
    rsync -az --progress keyring.debian.org::keyrings/keyrings/  ./data/keyrings/

### Run database maintenance
    
    ./manage.py maintenance

### Run the web server
    
    ./manage.py runserver


## Periodic updates
You need to run periodic maintenance to check/regenerate the denormalised
fields:

    ./manage.py maintenance


## Development
Development targets Django 1.5, although the codebase has been created with
Django 1.2 and it still shows in some places. Feel free to cleanup.
