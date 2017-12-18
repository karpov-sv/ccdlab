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

```shell
command_name arg1 arg2 kwarg1=val1 kwarg2=val2
```

The following set of commands is common for all daemons:

  * **get_id** - requests peer identification
    * **id name=*name* type=*type* ** - identification reply, the peer name is *name*, type is *type*. These values will be used to identify the device and send commands to it from *MONITOR*

  * **get_status** - requests the daemon and device status
    * **status var1=value1 var2=value2 ...** - status reply giving the values of all status varables related to device or service

  * **exit** - stops the daemon

*MONITOR* service also accepts the following commands:

  * **send *client_name* command** - sends the command to named client

  * **clients** (console only) - prints the list of registered clients to console

  * **connections** (console only) - print the list of current connections to console

## MONITOR service

The service is intended for a continuous monitoring of all registered device daemons or other services, and provides both (primitive) console interface and a configurable Web interface.
