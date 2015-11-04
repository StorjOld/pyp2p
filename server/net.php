<?php

$action = $_GET["action"];
if($action == "get_wan_ip")
{
    echo($_SERVER['REMOTE_ADDR']);
}

if($action == "is_port_forwarded")
{
    $port = $_GET["port"];
    $proto = strtoupper($_GET["proto"]);
    $response = '{"result": "no"}';
    $try = 1;
    while($try)
    {
        #Break the loop.
        $try = 0;

        #Invalid port.
        if(preg_match("/^[0-9]+$/i", $port) != 1)
        {
            break;
        }
        if($port < 1 || $port > 65535)
        {
            break;
        }

        #Invalid proto.
        $valid_protos = array("TCP", "UDP");
        if(!in_array($proto, $valid_protos))
        {
            break;
        }

        #Test connection (UDP is currently ignored.)
        $ip = $_SERVER['REMOTE_ADDR'];
        $fp = @fsockopen("tcp://" . $ip, $port, $errno, $errstr, 1.0);
        if($fp)
        {
            fclose($fp);
            $response = '{"result": "yes"}';
        }
        $fp = 0;

        break;
    }

    echo $response;
}

?>
