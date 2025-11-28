from frontend_private.views.experiments import ExperimentDangerZoneView
from frontend_private.views.experiments import ExperimentDataViewerView
from frontend_private.views.experiments import ExperimentDetailsView
from frontend_private.views.experiments import ExperimentGISView
from frontend_private.views.experiments import ExperimentListingView
from frontend_private.views.experiments import ExperimentUserPermissionsView
from frontend_private.views.experiments import NewExperimentView
from frontend_private.views.gis_views import GISViewDangerZoneView
from frontend_private.views.gis_views import GISViewDetailsView
from frontend_private.views.gis_views import GISViewGISIntegrationView
from frontend_private.views.gis_views import GISViewListingView
from frontend_private.views.gis_views import NewGISViewView
from frontend_private.views.map import MapViewerView
from frontend_private.views.project import NewProjectView
from frontend_private.views.project import ProjectDangerZoneView
from frontend_private.views.project import ProjectDetailsView
from frontend_private.views.project import ProjectGitExplorerView
from frontend_private.views.project import ProjectGitInstructionsView
from frontend_private.views.project import ProjectListingView
from frontend_private.views.project import ProjectMutexesView
from frontend_private.views.project import ProjectRevisionHistoryView
from frontend_private.views.project import ProjectTeamPermissionsView
from frontend_private.views.project import ProjectUploadView
from frontend_private.views.project import ProjectUserPermissionsView
from frontend_private.views.sensor_fleets import NewSensorFleetView
from frontend_private.views.sensor_fleets import SensorFleetDangerZoneView
from frontend_private.views.sensor_fleets import SensorFleetDetailsView
from frontend_private.views.sensor_fleets import SensorFleetHistoryView
from frontend_private.views.sensor_fleets import SensorFleetListingView
from frontend_private.views.sensor_fleets import SensorFleetUserPermissionsView
from frontend_private.views.sensor_fleets import SensorFleetWatchlistView
from frontend_private.views.surface_networks import NewSurfaceNetworkView
from frontend_private.views.surface_networks import SurfaceNetworkDangerZoneView
from frontend_private.views.surface_networks import SurfaceNetworkDetailsView
from frontend_private.views.surface_networks import SurfaceNetworkGISView
from frontend_private.views.surface_networks import SurfaceNetworkListingView
from frontend_private.views.surface_networks import SurfaceNetworkUserPermissionsView
from frontend_private.views.team import NewTeamView
from frontend_private.views.team import TeamDangerZoneView
from frontend_private.views.team import TeamDetailsView
from frontend_private.views.team import TeamListingView
from frontend_private.views.team import TeamMembershipsView
from frontend_private.views.tools import ToolDMP2Json
from frontend_private.views.tools import ToolDMPDoctor
from frontend_private.views.tools import ToolXLSToArianeDMP
from frontend_private.views.tools import ToolXLSToCompass
from frontend_private.views.user import AuthTokenView
from frontend_private.views.user import DashboardView
from frontend_private.views.user import FeedbackView
from frontend_private.views.user import PassWordView
from frontend_private.views.user import PreferencesView
from frontend_private.views.user import StationTagsView

__all__ = [
    "AuthTokenView",
    "DashboardView",
    "ExperimentDangerZoneView",
    "ExperimentDataViewerView",
    "ExperimentDetailsView",
    "ExperimentGISView",
    "ExperimentListingView",
    "ExperimentUserPermissionsView",
    "FeedbackView",
    "GISViewDangerZoneView",
    "GISViewDetailsView",
    "GISViewGISIntegrationView",
    "GISViewListingView",
    "MapViewerView",
    "NewExperimentView",
    "NewGISViewView",
    "NewProjectView",
    "NewSensorFleetView",
    "NewSurfaceNetworkView",
    "NewTeamView",
    "PassWordView",
    "PreferencesView",
    "ProjectDangerZoneView",
    "ProjectDetailsView",
    "ProjectGitExplorerView",
    "ProjectGitInstructionsView",
    "ProjectListingView",
    "ProjectMutexesView",
    "ProjectRevisionHistoryView",
    "ProjectTeamPermissionsView",
    "ProjectUploadView",
    "ProjectUserPermissionsView",
    "SensorFleetDangerZoneView",
    "SensorFleetDetailsView",
    "SensorFleetHistoryView",
    "SensorFleetListingView",
    "SensorFleetUserPermissionsView",
    "SensorFleetWatchlistView",
    "StationTagsView",
    "SurfaceNetworkDangerZoneView",
    "SurfaceNetworkDetailsView",
    "SurfaceNetworkGISView",
    "SurfaceNetworkListingView",
    "SurfaceNetworkUserPermissionsView",
    "TeamDangerZoneView",
    "TeamDetailsView",
    "TeamListingView",
    "TeamMembershipsView",
    "ToolDMP2Json",
    "ToolDMPDoctor",
    "ToolXLSToArianeDMP",
    "ToolXLSToCompass",
]
