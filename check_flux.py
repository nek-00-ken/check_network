import subprocess
import os
import getpass
import json
import sys
import getopt
from os import path

# glob vars
glob_binaries = ["ssh"]


def check_prerequisites():
    res = True
    for binary in glob_binaries:
        cmd = subprocess.Popen(["which", binary], stdout=subprocess.PIPE)
        if len(cmd.stdout.readlines()) == 0:
            print("You must install following package : " + binary)
            res = False

    return res


def print_usage():
    for binary in glob_binaries:
        print("Package to install : %s" % binary)
    print('USAGE : check_flux.py -c <file> [-s (OK|NOK)] [-m <machine (hostname)>]')


def get_password(env_var):
    password = os.getenv(env_var)
    if password is None:
        password = getpass.getpass(env_var + ' environment variable is not defined, please enter password to use : ')
        if password is "":
            print("Your password is empty")
            exit(1)
    return password


def read_config(file):
    '''
    :param file: path to config file
    :return: a tuple, each element is a section represented by 1 of the top-level
    attribute in the config JSON file
    '''
    if file is None:
        print("You must specify a configuration file !")
        print_usage()
        exit(1)

    if not path.isfile(file):
        print("file : %s does not exists" % file)
        print_usage(1)

    config = json.loads(open(file, 'r').read())

    return config['groups'], config['hosts']


def check_rules(host, json_attribute_name, display_status):
    __login = host['login']
    __ip_address = host['ip_address']
    __connection = __login + "@" + __ip_address
    __from_host_name = host['hostname']
    __ssh_key_path = host['ssh_key']
    __label = host['label']
    __rules = host[json_attribute_name]

    # prepare command
    hosts_list = ""
    for rule in __rules:
        dest = rule['dest_hostname'] if rule['dest_hostname'] else rule['dest_ip']
        port = str(rule['dest_port'])
        hosts_list += dest + ":" + port + " "

    loop_cmd = "for i in `echo \"" + hosts_list + "\" ` ;"
    loop_cmd += "do echo 'quit' | nc -w 5 `echo $i | cut -d\":\" -f1` `echo $i | cut -d\":\" -f2` >& /dev/null; "
    loop_cmd += "echo $?; done"

    cmd = " ".join(("ssh", "-o StrictHostKeyChecking=no", "-i", __ssh_key_path, __connection, "'", loop_cmd, "'"))

    # execute command
    ps = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # parse result
    stdouts = []

    while True:
        line = ps.stdout.readline()
        if line != '':
            stdouts.append(line.rstrip())
        else:
            break

    # display results

    # display header
    print("\n" + '*' * 100)
    print(__label.rjust(40) + " (" + __from_host_name + " / " + __ip_address + ") ==> " + json_attribute_name.upper())
    print('*' * 100)
    print('STATE'.ljust(7) + 'FROM'.ljust(20) + 'TO'.ljust(40) + 'PORT'.ljust(8) + 'DESCRIPTION')
    print('-' * 100)

    # display rules
    i = 0
    for rule in __rules:
        dest = rule['dest_hostname'] if rule['dest_hostname'] else rule['dest_ip']
        port = str(rule['dest_port'])
        description = rule['description']
        status = 'OK' if stdouts[i] == "0" else 'NOK'

        if display_status is None or status == display_status:
            print("".join((status.ljust(7), __from_host_name.ljust(20), dest.ljust(40), port.ljust(8), description)))

        i += 1


def get_hosts_from_group_name(groups, label):
    for group in groups:
        if group['label'] == label:
            return group


def main():
    check_prerequisites()

    input_file = None
    display_only_status = None
    filter_hostname = None
    filter_group_label = None
    # group_hosts = None

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hc:s:m:g:")
    except getopt.GetoptError:
        print_usage(1)

    for opt, arg in opts:
        if opt == '-h':
            print_usage(0)
        elif opt == "-c":
            input_file = arg
        elif opt == "-s":
            if not arg in ['OK', 'NOK']:
                print('Bad value for status !')
                print_usage(1)
            display_only_status = arg
        elif opt == "-m":
            filter_hostname = arg
        elif opt == "-g":
            filter_group_label = arg

    groups, hosts = read_config(input_file)

    for host in hosts:
        if filter_hostname is not None and host['hostname'] != filter_hostname:
            continue

        if filter_group_label is not None:
            group_hosts = get_hosts_from_group_name(groups, filter_group_label)

            if group_hosts is None:
                print('The group "' + filter_group_label + '" does not exist')
                exit(1)

            if not host['hostname'] in group_hosts['hosts']:
                continue

        if 'services' in host:
            check_rules(host, 'services', display_only_status)

        if 'flux' in host:
            check_rules(host, 'flux', display_only_status)


main()