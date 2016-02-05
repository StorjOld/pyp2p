<?php

require_once("config.php");

function start_transaction($con)
{
    mysql_query("BEGIN", $con);
    mysql_query("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE", $con);
}

function end_transaction($con, $success)
{
    if($success)
    {
        mysql_query("COMMIT", $con);
    }
    else
    {
        mysql_query("ROLLBACK", $con);
    }
}

function count_fresh_nodes($con)
{
    global $config;
    
    $freshness = time() - $config["alive_timeout"];
    $sql = "SELECT COUNT(DISTINCT `id`) as total FROM `nodes` WHERE `last_alive` >= $freshness";
    $result = mysql_query($sql, $con);
    $data = mysql_fetch_assoc($result);
    $data = $data['total'];
    
    return $data;
}

function get_con()
{
    global $config;

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

    return $con;
}

function get_node($node_id)
{
    global $con;
    
    $node_id = mysql_real_escape_string($node_id, $con);
    $sql = "SELECT * FROM `nodes` WHERE `node_id`='$node_id';";
    $result = mysql_query($sql, $con);
    $ret = mysql_fetch_assoc($result);
    
    return $ret;
}

function get_messages($node_id, $list_pop)
{
    global $con;
    
    $node_id = mysql_real_escape_string($node_id, $con);
    $sql = "SELECT * FROM `messages` WHERE `node_id`='$node_id' AND `list_pop`=$list_pop";
    $result = mysql_query($sql, $con);
    $messages = array();
    $old_ids = array();
    while($row = mysql_fetch_assoc($result))
    {
        $messages[] = $row["message"];
        $old_ids[] = $row["id"];
    }
    
    return array ($messages, $old_ids);
}

function check_password($node_id, $password)
{
    global $con;
    
    $password = mysql_real_escape_string($password, $con);
    $node = get_node($node_id);
    if($node == FALSE)
    {
        return 0;
    }
    if($node["password"] != $password)
    {
        return 0;
    }
    
    return $node;
}

function node_last_alive($node)
{
    global $con;
    
    $id = mysql_real_escape_string($node["id"]);
    $last_alive = time();
    $sql = "UPDATE `nodes` SET `last_alive`=$last_alive WHERE `id`=$id";
    mysql_query($sql, $con);
}

function cleanup_messages()
{
    global $con;
    
    $timestamp = time();
    $sql = "DELETE FROM `messages` WHERE `cleanup_expiry`<=$timestamp";
    mysql_query($sql, $con);
}

?>
