Plugin loading order
====================

/----------------------------------\             +----------------------------------------+
| are we inside the admin console? | --- no ---> |                  exit                  |
\----------------------------------/             +----------------------------------------+
                 |
                yes
                 |
                 v
+----------------------------------+             +----------------------------------------+
|                                  |             |      bootstrap global defaults and     |
|   register the activate method   |------------>|          options on first run          |
|                                  |             |      check global defaults version     |
+----------------------------------+             +----------------------------------------+
                 |
                 v
+----------------------------------+             +----------------------------------------+
|  register the plugins_loaded     |------------>|       bootstrap blog options and       |
|             method               |             |        1st stage blog defaults         |
+----------------------------------+             +----------------------------------------+
                 |                                                  |
                 |                                                  v
                 |                               +----------------------------------------+
                 |                               |       register actions for active      |
                 |                               |         wp_frontman blog options       |
                 |                               +----------------------------------------+
                 |
                 v
+----------------------------------+             +----------------------------------------+
|    register the init method      |------------>|    bootstrap 2nd stage blog defaults   |
|                                  |             |        check blog options version      |
+----------------------------------+             +----------------------------------------+
