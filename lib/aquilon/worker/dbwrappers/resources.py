# -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# ex: set expandtab softtabstop=4 shiftwidth=4:
#
# Copyright (C) 2011,2012,2013,2014  Contributor
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Wrappers to make getting and using systems simpler."""

from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm import object_session
from sqlalchemy.inspection import inspect

from aquilon.exceptions_ import (IncompleteError, NotFoundException,
                                 ArgumentError)
from aquilon.aqdb.model import (Cluster, MetaCluster, ClusterResource,
                                HostResource, Resource, ResourceGroup,
                                BundleResource, RebootIntervention)
from aquilon.worker.templates import Plenary
from aquilon.worker.dbwrappers.host import hostname_to_host
from aquilon.worker.locks import CompileKey


def get_resource_holder(session, logger, hostname=None, cluster=None,
                        metacluster=None, resgroup=None, compel=True):
    who = None
    if hostname is not None:
        dbhost = hostname_to_host(session, hostname)
        who = dbhost.resholder
        if who is None:
            if compel:
                raise NotFoundException("{0} has no resources.".format(dbhost))
            dbhost.resholder = HostResource(host=dbhost)
            session.add(dbhost.resholder)
            session.flush()
            who = dbhost.resholder

    if cluster is not None:
        # TODO: disallow metaclusters here
        dbcluster = Cluster.get_unique(session, cluster, compel=True)
        if isinstance(dbcluster, MetaCluster):
            logger.client_info("Please use the --metacluster option for "
                               "metaclusters.")
        who = dbcluster.resholder
        if who is None:
            if compel:
                raise NotFoundException("{0} has no resources.".format(dbcluster))
            dbcluster.resholder = ClusterResource(cluster=dbcluster)
            session.add(dbcluster.resholder)
            session.flush()
            who = dbcluster.resholder

    if metacluster is not None:
        dbmeta = MetaCluster.get_unique(session, metacluster, compel=True)
        who = dbmeta.resholder
        if who is None:
            if compel:
                raise NotFoundException("{0} has no resources.".format(dbmeta))
            dbmeta.resholder = ClusterResource(cluster=dbmeta)
            session.add(dbmeta.resholder)
            session.flush()
            who = dbmeta.resholder

    if resgroup is not None:
        dbrg = ResourceGroup.get_unique(session, name=resgroup, holder=who,
                                        compel=True)
        who = dbrg.resholder
        if who is None:
            if compel:
                raise NotFoundException("{0} has no resources.".format(dbrg))
            dbrg.resholder = BundleResource(resourcegroup=dbrg)
            session.add(dbrg.resholder)
            session.flush()
            who = dbrg.resholder

    return who


def get_resource(session, holder, **arguments_in):
    # Filter out arguments that are not resources
    arguments = dict()
    mapper = inspect(Resource)
    for key, value in arguments_in.items():
        if key in mapper.polymorphic_map and value is not None:
            arguments[mapper.polymorphic_map[key].class_] = value
        elif key == "reboot_intervention" and value is not None:
            # Sigh... Abbreviations are bad.
            arguments[RebootIntervention] = value

    # Resource groups are act both as resource and as holder. If there's another
    # resource type specified, then use it as a holder; if it is specified
    # alone, then use it as a resource.
    if ResourceGroup in arguments and len(arguments) > 1:
        rg_name = arguments.pop(ResourceGroup)
        if not holder.resholder:
            raise NotFoundException("{0} has no resources.".format(holder))
        dbrg = ResourceGroup.get_unique(session, name=rg_name,
                                        holder=holder.resholder, compel=True)
        holder = dbrg

    if arguments:
        if len(arguments) > 1:
            raise ArgumentError("Only one resource type should be specified.")

        if not holder.resholder:
            raise NotFoundException("{0} has no resources.".format(holder))

        cls, name = arguments.popitem()
        return cls.get_unique(session, name=name, holder=holder.resholder,
                              compel=True)
    return None


def del_resource(session, logger, dbresource, dsdb_callback=None, **arguments):
    holder = dbresource.holder
    holder_plenary = Plenary.get_plenary(holder.holder_object, logger=logger)
    remove_plenary = Plenary.get_plenary(dbresource, logger=logger)

    if hasattr(dbresource, 'resholder') and dbresource.resholder:
        # We have to tell the ORM that these are going to be deleted, we can't
        # just rely on the DB-side cascading
        del dbresource.resholder.resources[:]
    holder.resources.remove(dbresource)
    session.flush()

    with CompileKey.merge([remove_plenary.get_key(), holder_plenary.get_key()]):
        try:
            remove_plenary.stash()
            holder_plenary.stash()

            try:
                holder_plenary.write(locked=True)
            except IncompleteError:
                holder_plenary.remove(locked=True)

            remove_plenary.remove(locked=True)

            if dsdb_callback:
                dsdb_callback(session, logger, holder, dbresource, **arguments)
        except:
            holder_plenary.restore_stash()
            remove_plenary.restore_stash()
            raise

    return


def add_resource(session, logger, holder, dbresource, dsdb_callback=None,
                 **arguments):
    if dbresource not in holder.resources:
        holder.resources.append(dbresource)

    holder_plenary = Plenary.get_plenary(holder.holder_object, logger=logger)
    res_plenary = Plenary.get_plenary(dbresource, logger=logger)

    session.flush()

    with CompileKey.merge([res_plenary.get_key(), holder_plenary.get_key()]):
        try:
            holder_plenary.stash()
            res_plenary.write(locked=True)
            try:
                holder_plenary.write(locked=True)
            except IncompleteError:
                holder_plenary.remove(locked=True)

            if dsdb_callback:
                dsdb_callback(session, logger, dbresource, **arguments)

        except:
            res_plenary.restore_stash()
            holder_plenary.restore_stash()
            raise

    return


def walk_resources(dbobj):
    """
    Walk all resources of a resource holder

    Resource groups are expanded in a depth-first manner.
    """

    if not dbobj.resholder:
        return
    for res in dbobj.resholder.resources:
        if isinstance(res, ResourceGroup):
            walk_resources(res)
        else:
            yield res


def find_resource(cls, dbobj, resourcegroup, resource, ignore=None,
                  error=NotFoundException):
    """
    Find a suitable share or filesystem resource.

    dbobj is either a host, cluster, or metacluster. If dbobj is a cluster that
    is part of a metacluster, and the resource is not defined at the cluster
    level, then it is also searched for at the metacluster level. If
    resourcegroup is not None, the resource must be part of the named
    resourcegroup; otherwise, it must not be inside a resourcegroup.

    If the value of ignore is an existing Share or Filesystem instance, then
    that instance will be ignored by find_resource.
    """

    session = object_session(dbobj)

    if resourcegroup:
        dbrg = ResourceGroup.get_unique(session, name=resourcegroup,
                                        holder=dbobj.resholder)
        if dbrg:
            holder = dbrg.resholder
        else:
            holder = None
    else:
        holder = dbobj.resholder

    if holder:
        q = session.query(cls)
        q = q.filter_by(name=resource, holder=holder)
        if ignore:
            q = q.filter_by(id != ignore.id)

        # The (name, holder) pair is unique, so we cannot get multiple results
        # here
        try:
            return q.one()
        except NoResultFound:
            pass

    # No luck. If this was a cluster, try to find the resource at the metacluster
    # level, but if even that fails, report the problem for the cluster.
    if hasattr(dbobj, 'metacluster') and dbobj.metacluster:
        try:
            return find_resource(cls, dbobj.metacluster, resourcegroup, resource,
                                 ignore=ignore, error=error)
        except error:
            pass

    clslabel = cls._get_class_label().lower()

    if resourcegroup:
        msg = "{0} does not have {1} {2!s} assigned to it in " \
              "resourcegroup {3}.".format(dbobj, clslabel,
                                          resource, resourcegroup)
    else:
        msg = "{0} does not have {1} {2!s} assigned to it.".format(dbobj,
                                                                   clslabel,
                                                                   resource)

    raise error(msg)
