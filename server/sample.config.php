<?php

$config = array(
    "db" => array(
        "host" => "localhost",
        "name" => "dht_msg",
        "user" => "root",
        "pass" => "password"
    ),
    "long_polling" => True,
    "mutex_timeout" => (10 * 60), // Currently not used.
    "reservation_timeout" => (10 * 60), // Nodes are reserved for 10 minutes of testing.
    "alive_timeout" => (60 * 10), // Keep nodes very fresh.
    "message_timeout" => (60 * 60 * 24), // Old messages cleaned up daily.
    "neighbour_limit" => 5,
    "debug_mode" => 0
);

?>
