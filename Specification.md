# Airfi HomeAssistant Integration

This is an integration for HomeAssistant for an Airfi (https://www.airfi.fi) hardware air handling unit. 
It's main task is to exchange air and to heat air. it integrates all kinds of sensors and advanced functionality.

This integration integrates with HomeAssistant and interfaces with the Airfi device using Modbus over TCP. On the HomeAssistant (HA) side
the integration presents normal sensors and suitable devices. The integration should be able to handle multiple Airfi devices, as a user might
have several of them in a house.


## Setting up
When the integration is added to HA the user needs to be able to find one or more Airfi devices. The devices do send a packet with data over
multicast every few seconds. These packets contains the IP address, port and device data. The integration needs to listen for these announcement
packets and present all found devices to the user.

If the announcement packets are not receives due to network topology or filtering, then the user should be able to add a new device based on IP
and port. It should be easy to change the type of representation for a register, as I'm not too familiar with the HA data types. The data
provided by the Airfi unit represents temperatures, fan speeds, boost percentages, home/away states, error bitmasks etc.


## Communication
The communication is normal Modbus TCP. A maximum of 20 registers can be read at one time due to memory constraints on the device side. Reading
more results in an error. Only one Modbus client can be connected to the Airfi unit at one time.


## Configuration in HA
The user should be able to later add and remove Airfi devices. The polling interval in seconds should be configurable. Devices should be possible 
to rename or give an alias like "Guest house unit", "Second floor unit" etc in order to make them easier to manage. 


## Registers

The following input registers are defined. The strings are in Finnish. The registers will need to be in a structure so that it's easy
to provide translated register names for English, Swedish etc.

### Input registers
The input registers are read only.

| Register | Name                           |
|----------|--------------------------------|
| 1        | Airfi-hw versio                |
| 2        | Airfi-sw versio                |
| 3        | Modbus-rekisteriversio         |
| 4        | T1, Ulkoilman lämpötila        |
| 5        | T2, Tuloilman lämpötila        |
| 6        | T3, Poistoilman lämpötila      |
| 7        | T4, Jäteilman lämpötila        |
| 8        | T5, Tulo asuntoon /jälkikäynti |
| 9        | T6, Jäätymissuoja              |
| 11       | Poistopuhaltimen nopeus        |
| 12       | Tulopuhaltimen nopeus          |
| 13       | AUX3 mode                      |
| 14       | AUX4 mode                      |
| 15       | Takka                          |
| 16       | Kotona/Poissa tila             |
| 17       | Hätäseis -tila                 |
| 18       | Jäätymisvaarahälytys           |
| 19       | Koneen vikatila                |
| 20       | VARALLA                        |
| 21       | Tulopuhaltimen RPM             |
| 22       | Poistopuhaltimen RPM           |
| 23       | Mitattu kosteuspitoisuus       |
| 24       | Puhaltimen nopeus              |
| 25       | Pakko-ohjaus                   |
| 26       | Suoraohjaus on/off             |
| 27       | Suoraohjaus 0-100%             |
| 28       | Lämpötilan asetuspiste         |
| 29       | AUX3 asetuspiste               |
| 30       | AUX4 asetuspiste               |
| 31       | Suodattimen vaihtoväli         |
| 32       | E0-E8                          |
| 33       | AUX 3 luettu arvo              |
| 34       | AUX 4 luettu arvo              |
| 35       | Vakiopainesäätö tulo-hälytys   |
| 36       | Vakiopainesääty poisto-hälytys |
| 37       | Suodatinvahtihälytys           |
| 38       | AUX2 tila                      |
| 39       | Fire alarm                     |
| 40       | Liesikuvun kompensointi        |
| 41       | S1 luettu arvo                 |
| 42       | Huone-anturi                   |
| 43       | Jälkilämmitys venttiili        |
| 44       | Defrost on                     |
| 45       | Intake pressure                |
| 46       | exhaust pressure               |
| 47       | AUX1 status                    |
| 48       | Status out valve control       |
| 49       | Bypass active status           |


### Holding registers
The following holding registers can be written. The table lists the register ids and the minimum and maximum
values for the registers.

| Register | Name                             | Min value | Max value |
|----------|----------------------------------|-----------|-----------|
| 1        | Nopeus                           | 0         | 5         |
| 2        | Pakko-ohjaus                     | 0         | 3         |
| 3        | Suoraohjaus käytössä             | 0         | 1         |
| 4        | Suoraohjaus 0-100%               | 0         | 100       |
| 5        | Lämpötilan asetuspiste           | 170       | 260       |
| 6        | AUX3 asetuspiste, minValue=0     | 2000      | True      |
| 7        | AUX4 asetuspiste                 | 0         | 100       |
| 8        | Suodattimen vaihtoväli           | 1         | 6         |
| 9        | Vakiopainesäätö tila, minValue=0 | 2         | True      |
| 10       | Tulopuhaltimen suoraohjaus       | 0         | 100       |
| 11       | Poistopuhaltimen suoraohjaus     | 0         | 100       |
| 12       | Kotona/poissa                    | 0         | 1         |
| 13       | VP, tulo, nop1 asetusarvo        | 0         | 999       |
| 14       | VP, tulo, nop2 asetusarvo        | 0         | 999       |
| 15       | VP, tulo, nop3 asetusarvo        | 0         | 999       |
| 16       | VP, tulo, nop4 asetusarvo        | 0         | 999       |
| 17       | VP, tulo, nop5 asetusarvo        | 0         | 999       |
| 18       | VP, poisto, nop1 asetusarvo      | 0         | 999       |
| 19       | VP, poisto, nop2 asetusarvo      | 0         | 999       |
| 20       | VP, poisto, nop3 asetusarvo      | 0         | 999       |
| 21       | VP, poisto, nop4 asetusarvo      | 0         | 999       |
| 22       | VP, poisto, nop5 asetusarvo      | 0         | 999       |
| 23       | VP, poikkeama-asetusarvo         | 5         | 300       |
| 24       | Suodatinvahti tila               | 0         | 2         |
| 25       | Suodatinvahti tulo ref.pnt       | 5         | 999       |
| 26       | Suodatinvahti poisto ref.pnt     | 5         | 999       |
| 27       | Emergency stop,manual resume     | 0         | 1         |
| 28       | Lähetintoiminto ohjauskerroin    | 0         | 999       |
| 29       | Lähetintoiminto poikkeama        | 0         | 999       |
| 30       | Palovaara tulo lämpöraja         | 0         | 99        |
| 31       | Palovaara poisto lämpöraja       | 0         | 99        |
| 32       | Jälkituuletus aika               | 0         | 10        |
| 33       | Buzzer sammutus                  | 0         | 1         |
| 34       | Suodattimen vaihtomuistutus      | 0         | 1         |
| 35       | Tulopuhallin nop1                | 25        | 100       |
| 36       | Tulopuhallin nop2                | 25        | 100       |
| 37       | Tulopuhallin nop3                | 25        | 100       |
| 38       | Tulopuhallin nop4                | 25        | 100       |
| 39       | Tulopuhallin nop5                | 25        | 100       |
| 40       | Poistopuhallin nop1              | 25        | 100       |
| 41       | Poistopuhallin nop2              | 25        | 100       |
| 42       | Poistopuhallin nop3              | 25        | 100       |
| 43       | Poistopuhallin nop4              | 25        | 100       |
| 44       | Poistopuhallin nop5              | 25        | 100       |
| 45       | Erilliset tulopuhallinarvot      | 0         | 1         |
| 46       | Tulopuhaltimen korjaus %         | 1         | 199       |
| 47       | Ohituksen asetuslämpötila        | 15        | 30        |
| 48       | Ohituksen sallittu alaraja       | 1         | 30        |
| 49       | Ohituksen viive                  | 5         | 30        |
| 50       | Tuloilman minimi asetus          | 10        | 25        |
| 51       | Tehostettu viilennys sallittu    | 0         | 1         |
| 52       | Lämpötilan asetusp. poissa       | 50        | 260       |
| 53       | Viilennyskäytön lämpötilaraja    | 10        | 99        |
| 54       | Esilämmityksen lämpötilaraja     | 2         | 99        |
| 55       | Outdoor valve manual state       | 0         | 1         |
| 56       | Internal RH sensor mode          | 0         | 2         |
| 57       | Sauna                            | 0         | 1         |
| 58       | Takka                            | 0         | 1         |
| 59       | Rotary disable                   | 0         | 1         |
| 60       | CO2 set value                    | 0         | 10000     |
| 61       | internal CO2 enabled             | 0         | 1         |
| 62       | Boost time (min,                 | 0         | 120       |
| 63       | Boost speed addition, percent    | 0         | 100       |
| 64       | Boost block                      | 0         | 4         |
| 65       | AUX1 status                      | 0         | 1         |
| 66       | Modbus RH sensor                 | 0         | 100       |
| 67       | Modbus CO2 sensor                | 0         | 10000     |
| 68       | Modbus temperature sensor        | 0         | 65536     |


## Integration details

The name of the integration is `airfi`. The units and scaling for each register needs to be filled in later. For now guess a suitable
unit for each register and use an empty string for those that are not clear. The scaling for each value is 1 by default, but add in a
field where the scaling can be set.

