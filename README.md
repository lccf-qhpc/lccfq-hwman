# lccfq-hwman
Hardware manager for the Pfafflab QPU





# How to setup

The following is still a work in progress but starts having some directions to how to start the service.

The hwman is designed to be running on a computer that has a connnection to the external network and a second connection to a pure intranet network. The QICK board should be located in that internal intranet. Remember to set the ssh config such that the hwman can ssh into the QICK board without adding a password, this is important for the hwman to be able to start the QICK service automatically. The qick board needs to have a script with all the correct configurations already in there. The hwman pc also needs to have ssh setup correctly to ssh into the qickboard itself without the use a password (using ssh keys)