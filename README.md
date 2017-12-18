# CCDLab
Software for a CCD testing lab at Fyzikální ústav AV ČR

## Introduction

We have decided to create our own, very small software framework for integrating various devices (sensors, CCD controllers etc) into a network to easily monitor their state and access from scripts.

Basic principles we will follow:

  * Every device is accessed through a dedicated daemon, always running and always monitoring device state
  * Every daemon is accessible over the network using simple, text line-based protocol
  * Every daemon accepts commands for both reporting the device state and changing it. It is daemon responsibility to check the validity of state changing commands and reject them if necessary
  * Dedicated *MONITOR* service is always running on the network, always polling all the devices for state changes, storing the data to database and providing simple Web interface for it
  * During the experiment, user-level scripts (written in any language) connect to every device they need, initiate state changing commands (e.g. setting the temperature), wait for a given state conditions (e.g. temperature stabilization) etc. The high level script logic is completely outside the scope of the software framework controlling the devices

## Command protocol

The protocol is based on simple newline- or null-terminated strings sent over TCP connection. There is an extension for sending binary data of a given length over the protocol connection.

Every command consists of a command name with positional or keyword arguments separated by whitespaces.

```
command_name arg1 arg2 kwarg1=val1 kwarg2=val2
```

The following set of commands is common for all daemons:

  * **get_id** - requests peer identification
    * **id name=*name* type=*type*** - identification reply, the peer name is *name*, type is *type*. These values will be used to identify the device and send commands to it from *MONITOR*

  * **get_status** - requests the daemon and device status
    * **status var1=value1 var2=value2 ...** - status reply giving the values of all status varables related to device or service

  * **exit** - stops the daemon

*MONITOR* service also accepts the following commands:

  * **send *client_name* command** - sends the command to named client

  * **clients** (console only) - prints the list of registered clients to console

  * **connections** (console only) - print the list of current connections to console

## MONITOR service

The service is intended for a continuous monitoring of all registered device daemons or other services, and provides both (primitive) console interface and a (configurable) Web interface.

```
> ./monitor.py --help
Usage: monitor.py [options] name1=host1:port1 name2=host2:port2 ...

Options:
  -h, --help            show this help message and exit
  -p PORT, --port=PORT  Daemon port
  -n NAME, --name=NAME  Daemon name
  -d, --debug           Debug output
```

The list of clients may either be provided on command line as a list of `name=host:port` expressions, or given in a configuration file. By default the code looks for `monitor.ini` file alongside with the `monitor.py` executable.

The format of configuration file is as follows:

```INI
port = integer(min=0,max=65535,default=7100) ; Monitor service port
name = string(default=monitor) ; Monitor service id name

[client_name] ; Section for a single client, may be repeated
enabled = boolean(default=True) ; The client may be disabled here
port = integer(min=0,max=65535,default=0) ; Client host
host = string(default=localhost) ; Client port
description = string(default=None) ; Client description
template = string(default=default.html) ; HTML template to use for rendering client state

[[plots]] ; Sub-section for client plots
[[[plot_id]]] ; Single plot definition, may be repeated
name = string(default=None) ; Free-form plot title
values = list(default=,) ; List of variables to plot
xlabel = string(default=None)
ylabel = string(default=None)
width = integer(min=0,max=2048,default=800)
height = integer(min=0,max=2048,default=300)
```

All the fields may be skipped, default values will be used instead. The parameters provided on command line take precedence - i.e. by specifying the same `client_name` as listed in config file, the host and port may be changed keeping all other client parameters intact.

The plots are configured as a lists of variable names from a client status string, along with special `time` variable. The first variable is used as abscissa, all the following - as ordinates. The plot is titled with a freeform name, has configurable x and y axes labels (if not provided, some sensible defaults will be used) and is accessed on the Web at `/monitor/plot/client_name/plot_id`.

The web interface is accessible at `localhost:8888` by default, and contains a header with list of all registered clients and their connection statuses, the command line to send commands to the service, and an information blocks for every client. Default information block (as defined in `default.html` template) simply lists all the variables reported by status reply, as well as all the plots configured for client. More sophisticated, device-specific views may be defined.

The templates reside in `web/template/` folder. `monitor.html` defines the overall look of *MONITOR* web page, while `default.html` - default client information block.


## Scripted access to the system

You may access from shell or your script either device daemons directly, or *MONITOR* service which already holds the connections to all configured devices and allows sending arbitrary commands to them.

Below is an example of how to do it in Python.

```python
from telnetlib import Telnet
from command import Command
from time import sleep

def send_message_wait_reply(message, replies=[], host='localhost', port=7100):
    t = Telnet(host, port)
    t.write('%s\n' % message)
    
    if replies:
        while True:
            reply = t.read_until('\n')
            cmd = Command(reply)
            
            if cmd.name in replies:
                t.close()
                return cmd
            
# Request status of all devices from monitor
status = send_message_wait_reply('get_status', replies=['status']).kwargs
print status

# Send command and wait for specific condition 
send_message_wait_reply('send cryocon set temperature=-100')
while True:
    sleep(10)
    status = send_message_wait_reply('get_status', replies=['status']).kwargs
    print "CryoCon temperature:", status['cryocon_temperature']
    if float(status['cryocon_temperature']) < -99.9:
        print "CryoCon temperature reached"
        break

    
```

## Supported devices

...

## TODO

  * Storing logs (for all daemons?) and status variables (for *MONITOR* service) to database
  * Acquiring and storing FITS images with proper meta-information in headers
  * Displaying acquired images in *MONITOR* web interface
  
