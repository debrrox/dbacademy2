from typing import Callable, List, TypeVar

from dbacademy import dbgems


class WorkspaceHelper:
    from dbacademy.dbhelper.dbacademy_helper_class import DBAcademyHelper
    from dbacademy.dbrest import DBAcademyRestClient

    T = TypeVar("T")

    PARAM_LAB_ID = "lab_id"
    PARAM_DESCRIPTION = "description"
    PARAM_CONFIGURE_FOR = "configure_for"

    CONFIGURE_FOR_ALL_USERS = "All Users"
    CONFIGURE_FOR_MISSING_USERS_ONLY = "Missing Users Only"
    CONFIGURE_FOR_CURRENT_USER_ONLY = "Current User Only"

    CONFIGURE_FOR_OPTIONS = ["", CONFIGURE_FOR_ALL_USERS, CONFIGURE_FOR_MISSING_USERS_ONLY, CONFIGURE_FOR_CURRENT_USER_ONLY]
    CONFIGURE_FOR_VALID_OPTIONS = CONFIGURE_FOR_OPTIONS[1:]  # all but empty-string

    @staticmethod
    def get_lab_id():
        return dbgems.get_parameter(WorkspaceHelper.PARAM_LAB_ID)

    @staticmethod
    def get_workspace_name():
        return dbgems.get_spark_config("spark.databricks.workspaceUrl", default=dbgems.get_notebooks_api_endpoint())

    @staticmethod
    def get_workspace_description():
        return dbgems.get_parameter(WorkspaceHelper.PARAM_DESCRIPTION)

    def __init__(self, da: DBAcademyHelper):
        from .warehouses_helper_class import WarehousesHelper
        from .databases_helper_class import DatabasesHelper
        from .clusters_helper_class import ClustersHelper

        self.da = da
        self.client = da.client
        self.warehouses = WarehousesHelper(self, da)
        self.databases = DatabasesHelper(self, da)
        self.clusters = ClustersHelper(self, da)

        self._usernames = None
        self._existing_databases = None

    @staticmethod
    def add_entitlement_allow_instance_pool_create(client: DBAcademyRestClient):
        group = client.scim.groups.get_by_name("users")
        client.scim.groups.add_entitlement(group.get("id"), "allow-instance-pool-create")

    @staticmethod
    def add_entitlement_workspace_access(client: DBAcademyRestClient):
        group = client.scim.groups.get_by_name("users")
        client.scim.groups.add_entitlement(group.get("id"), "workspace-access")

    @staticmethod
    def add_entitlement_allow_cluster_create(client: DBAcademyRestClient):
        group = client.scim.groups.get_by_name("users")
        client.scim.groups.add_entitlement(group.get("id"), "allow-cluster-create")

    @staticmethod
    def add_entitlement_databricks_sql_access(client: DBAcademyRestClient):
        group = client.scim.groups.get_by_name("users")
        client.scim.groups.add_entitlement(group.get("id"), "databricks-sql-access")

    def do_for_all_users(self, f: Callable[[str], T]) -> List[T]:
        from multiprocessing.pool import ThreadPool

        # if self.usernames is None:
        #     raise ValueError("DBAcademyHelper.workspace.usernames must be defined before calling DBAcademyHelper.workspace.do_for_all_users(). See also DBAcademyHelper.workspace.load_all_usernames()")
        if len(self.usernames) == 0:
            return []

        with ThreadPool(len(self.usernames)) as pool:
            return pool.map(f, self.usernames)

    @property
    def org_id(self):
        try:
            return dbgems.get_tag("orgId", "unknown")
        except:
            # dbgems.get_tags() can throw exceptions in some secure contexts
            return "unknown"

    @property
    def workspace_name(self):
        try:
            workspace_name = dbgems.get_browser_host_name()
            return dbgems.get_notebooks_api_endpoint() if workspace_name is None else workspace_name
        except:
            # dbgems.get_tags() can throw exceptions in some secure contexts
            return dbgems.get_notebooks_api_endpoint()

    @property
    def configure_for(self):
        from dbacademy.dbhelper import DBAcademyHelper
        # Under test, we are always configured for the current user only

        configure_for = WorkspaceHelper.CONFIGURE_FOR_CURRENT_USER_ONLY if DBAcademyHelper.is_smoke_test() else dbgems.get_parameter(WorkspaceHelper.PARAM_CONFIGURE_FOR)
        assert configure_for in WorkspaceHelper.CONFIGURE_FOR_VALID_OPTIONS, f"Who the workspace is being configured for must be specified, found \"{configure_for}\". Options include {WorkspaceHelper.CONFIGURE_FOR_VALID_OPTIONS}"
        return configure_for

    @property
    def usernames(self):
        if self._usernames is None:
            users = self.client.scim().users().list()
            self._usernames = [r.get("userName") for r in users]
            self._usernames.sort()

        if self.configure_for == WorkspaceHelper.CONFIGURE_FOR_CURRENT_USER_ONLY:
            # Override for the current user only
            return [self.da.username]

        elif self.configure_for == WorkspaceHelper.CONFIGURE_FOR_MISSING_USERS_ONLY:
            # TODO - This isn't going to hold up long-term, maybe track per-user properties in this respect.
            # The presumption here is that if the user doesn't have their own
            # database, then they are also missing the rest of their config.
            missing_users = set()

            for username in self._usernames:
                prefix = self.da.to_schema_name_prefix(username=username, course_code=self.da.course_config.course_code)
                for schema_name in self.existing_databases:
                    if schema_name.startswith(prefix):
                        missing_users.add(username)

            missing_users = list(missing_users)
            missing_users.sort()
            return missing_users

        return self._usernames

    @property
    def existing_databases(self):
        if self._existing_databases is None:
            existing = dbgems.spark.sql("SHOW DATABASES").collect()
            self._existing_databases = {d[0] for d in existing}
        return self._existing_databases

    @property
    def lab_id(self):
        from dbacademy.dbhelper import DBAcademyHelper
        lab_id = "Smoke Test" if DBAcademyHelper.is_smoke_test() else dbgems.get_parameter(WorkspaceHelper.PARAM_LAB_ID, None)
        return None if lab_id is None else dbgems.clean_string(lab_id)

    @property
    def description(self):
        from dbacademy.dbhelper import DBAcademyHelper
        description = "This is a smoke test" if DBAcademyHelper.is_smoke_test() else dbgems.get_parameter(WorkspaceHelper.PARAM_DESCRIPTION, None)
        return None if description is None else dbgems.clean_string(description)
