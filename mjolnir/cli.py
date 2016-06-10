import logging

import click
import etcd
from midonetclient import client as mc

KEY = '/midonet/agents/'


@click.command()
@click.option('--tunnel-zone', default='default', help='Name of the tunnel '
              'zone to add the hosts to.')
@click.option('--encapsulation', default='vxlan', help='Encapsulation '
              'technology to use for the tunnel if it does not exist yet. It '
              'can be either vxlan or gre.')
@click.option('--midonet-url', default='http://localhost:8181/midonet-api/',
              help='Endpoint to access the MidoNet cluster.')
@click.option('--username', default='admin',
              help='Keystone admin username to talk to the MidoNet '
              'cluster.')
@click.option('--password', default='admin',
              help='Keystone admin password to talk to the MidoNet '
              'cluster.')
@click.option('--project', default='admin',
              help='Keystone admin project name to talk to the MidoNet '
              'cluster.')
@click.option('--etcd-host', default='localhost',
              help='Address to an etcd server.')
@click.option('--etcd-port', default=4001,
              help='Port to an etcd server.')
def register(tunnel_zone, encapsulation,
             midonet_url, username, password, project,
             etcd_host, etcd_port):
    """Watches cluster store and registers the hosts into the MidoNet cluster

    It watches /midonet/agents/[uuid] keys and values and adds them to the
    specified tunnel zone
    """
    etclient = etcd.Client(host=etcd_host, port=etcd_port)
    midoclient = mc.MidonetClient(midonet_url, username, password,
                                  project_id=project)
    tz = _ensure_tunnel_zone(midoclient, tunnel_zone, encapsulation)
    uuids = set(host.get_host_id() for host in tz.get_hosts())

    current_index, uuids = _catchup(etclient, tz, uuids)
    for event in etclient.eternal_watch(KEY, index=current_index,
                                        recursive=True):
        for host in event.get_subtree(leaves_only=True):
            # TODO: get when an event is removed
            if host.key in uuids:
                logging.info('Host %s already in tunnel zone %s', host.key,
                             host.value)
            else:
                try:
                    _add_to_tunnel_zone(tunnel_zone, host.key, host.value)
                except Exception:
                    continue  # at least try to add the rest
                else:
                    uuids.add(host.key)


def _catchup(client, tunnel_zone, uuids):
    """Updates the MidoNet cluster to the current state in /midonet/agents"""
    result = client.read(KEY, recursive=True)

    for host in result.get_subtree(leaves_only=True):
        if host.key in uuids:
            logging.info('Host %s already in tunnel zone %s', host.key,
                         host.value)
        else:
            try:
                _add_to_tunnel_zone(tunnel_zone, host.key, host.value)
            except Exception:
                continue  # at least try to add the rest
            else:
                uuids.add(host.key)

    return result.etcd_index, uuids


def _add_to_tunnel_zone(tunnel_zone, uuid, address):
    new_tz_host = tunnel_zone.add_tunnel_zone_host()
    new_tz_host.host_id(uuid)
    new_tz_host.ip_address(address)
    try:
        new_tz_host.create()
    except Exception:
        logging.exception('Failed to add host %s with address %s to '
                          'the default tunnel zone', uuid, address)
    else:
        logging.info('host %s with address: %s added to the default '
                     'tunnel zone', uuid, address)


def _ensure_tunnel_zone(conn, name, encapsulation):
    tunnel_zones = [tz for tz in conn.get_tunnel_zones() if
                    tz.get_name() == name]

    if tunnel_zones:
        tz = tunnel_zones[0]
    else:
        ntz = conn.add_tunnel_zone()
        ntz.type(encapsulation)
        ntz.name(name)
        try:
            ntz.create()
        except Exception as ex:
            logging.error('Failed to create the default tunnel zone. Err: %s',
                          ex)
        tz = conn.get_tunnel_zone(ntz.get_id())
    return tz
