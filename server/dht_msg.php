<?php


#dht_msg.php?call=register&node_id=node&password=pass
#dht_msg.php?call=put&node_id=node&msg=test
#dht_msg.php?call=list&node_id=node&password=pass

require_once("config.php");

//Connect to DB.
$con = mysql_connect($config["db"]["host"], $config["db"]["user"], $config["db"]["pass"]);
if(!$con) {
    die('Not connected : ' . mysql_error());
}

//Select DB.
$db_selected = mysql_select_db($config["db"]["name"], $con);
if(!$db_selected) {
    die('Can\'t use foo : ' . mysql_error());
}

//No cache.
header("Expires: Mon, 26 Jul 1997 05:00:00 GMT");
header("Cache-Control: no-cache");
header("Pragma: no-cache");

function get_node($node_id)
{
    global $con;

    $node_id = mysql_real_escape_string($node_id);
    $sql = "SELECT * FROM `nodes` WHERE `node_id`='$node_id';";
    $result = mysql_query($sql, $con);

    $ret = mysql_fetch_assoc($result);
    return $ret;
}

function get_messages($node_id)
{
    global $con;

    $node_id = mysql_real_escape_string($node_id);
    $sql = "SELECT * FROM `messages` WHERE `node_id`='$node_id';";
    $result = mysql_query($sql, $con);
    $messages = array();
    while($row = mysql_fetch_assoc($result)) {
        $messages[] = $row["message"];
    }

    return $messages;
}

$call = $_GET["call"];
$node_id = $_GET["node_id"];
if(!empty($call) && !empty($node_id))
{
    switch($call)
    {
        case "register":
            $password = $_GET["password"];
            if(empty($password))
            {
                break;
            }

            #Register new node.
            if(get_node($node_id) == FALSE)
            {
                $node_id = mysql_real_escape_string($node_id);
                $password = mysql_real_escape_string($password);
                $sql = "INSERT INTO `nodes` (`node_id`, `password`) VALUES ('$node_id', '$password');";
                mysql_query($sql);
            }

            break;

        case "put":
            $msg = $_GET["msg"];
            if(empty($msg))
            {
                break;
            }

            #Put message into DB.
            $msg = mysql_real_escape_string($msg);
            $node_id = mysql_real_escape_string($node_id);
            $sql = "INSERT INTO `messages` (`node_id`, `message`) VALUES ('$node_id', '$msg');";
            mysql_query($sql);
            break;

        case "list":
            $password = $_GET["password"];
            if(empty($password))
            {
                break;
            }

            #Check password.
            $password = mysql_real_escape_string($password);
            $node = get_node($node_id);
            if($node == FALSE)
            {
                break;
            }
            if($node["password"] != $password)
            {
                break;
            }

            #Get messages.
            $messages = get_messages($node_id);

            #Delete old messages.
            $node_id = mysql_real_escape_string($node_id);
            $sql = "DELETE FROM `messages` WHERE `node_id`='$node_id'";
            mysql_query($sql);

            #Return messages as JSON.
            echo(json_encode($messages));

            break;

        default:
            break;
    }
}

//All done.
mysql_close($con);

?>
