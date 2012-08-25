# file:///usr/share/doc/fabric/html/tutorial.html

from fabric.api import local, run, sudo, cd, env

env.hosts = ["nono.debian.org"]

def prepare_deploy():
    #local("./manage.py test my_app")
    #local("git add -p && git commit")
    local("test `git ls-files -cdmu | wc -l` = 0")
    local("git push")

def deploy():
    prepare_deploy()
    deploy_dir = "/srv/nm.debian.org/nm2"
    with cd(deploy_dir):
        sudo("git pull", user="nm")
        sudo("./manage.py collectstatic --noinput", user="nm")
        sudo("touch nm2.wsgi", user="nm")
