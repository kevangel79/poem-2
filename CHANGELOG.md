# Changelog

## [3.1.0] - 2020-03-30
### Added

* ARGO-1805 History of changes for Aggregation profiles
* ARGO-1811 Add validation logic for services missing in metric but presented in aggregation profile
* ARGO-1855 Clone feature for Metric profiles
* ARGO-1856 History of changes for Metric profiles
* ARGO-1993 Clone functionality for probes
* ARGO-1994 Expand metrics so that tenants can pick a version of the probe
* ARGO-2029 Introduce packages
* ARGO-2052 Introduce thresholds profiles
* ARGO-2077 border-success for newly created tuples in metric templates
* ARGO-2171 Metric template page on tenant POEM should show metric template history
* ARGO-2172 Filter metric templates by OS on tenant POEM
* ARGO-2208 Update version_comment if history entry is updated on super POEM
* ARGO-2232 History of changes for thresholds profiles
* ARGO-2249 Add description field to metric profiles
* ARGO-2265 Tag for packages to use it's present version from repo
* ARGO-2273 Introduce webpack watch mode
* ARGO-2286 React routes should be defined according to type of user
* ARGO-2289 Add link to thresholds profiles to administration page
* ARGO-2323 Add column with package name to probe list

### Fixed

* ARGO-2041 Use natural keys for serialization instead of primary keys
* ARGO-2044 Refactor history_helpers to properly handle missing fields in serialized_data
* ARGO-2073 Refactor tenant POEM internal code check
* ARGO-2074 Probe/metric template history breaks if the name is changed
* ARGO-2075 Load data from jsons not working when using natural keys for some models
* ARGO-2081 Multiple tuples delete does not work on Metric profiles
* ARGO-2083 Remove history button from groups of resources
* ARGO-2089 Tenant users should be able to add resources to groups associated to them
* ARGO-2091 Fix SAML2 login with Django 2.2
* ARGO-2231 Wrong probe version for certain metrics in repo API view
* ARGO-2252 Fix potential security issue as user can easily promote himself
* ARGO-2310 Super POEM session inspect should be properly called
* ARGO-2313 Metric templates states must be all set when render is triggered
* ARGO-2315 Fix syncers
* ARGO-2327 Metric configuration parameters should be clickable

### Changed

* ARGO-1960 Additional active session check next to isLogged localStorage key
* ARGO-2028 Refine Fontawesome icons
* ARGO-2072 Slimmer sidebar and footer
* ARGO-2078 Change title and remove unnecessary buttons from metric template clone view
* ARGO-2087 User without superuser permissions should not be able to add resources
* ARGO-2128 Refactor and simplify WEB-API and Backend API class and methods
* ARGO-2138 Change how probe and metric template history is handled in backend
* ARGO-2173 Remove button on metric templates not appearing properly
* ARGO-2174 Remove delete button from user addview
* ARGO-2175 Remove delete button from probe addview
* ARGO-2176 Remove delete button from group of resources addview
* ARGO-2218 Refactor token protected repo API view
* ARGO-2246 Harmonize profile change pages
* ARGO-2255 Refine version compare page for profiles
* ARGO-2284 API walk-through should filter and match content only for logged in user
* ARGO-2288 Remove "Staff status" checkbox from User UI
* ARGO-2290 Consistent table look across all pages
* ARGO-2324 Refactor sync_webapi function to create initial history entries

## [3.0.0] - 2019-11-08
### Added
* ARGO-1797 User/Pass and SAML2 Login and base UI structure
* ARGO-1798 Services page
* ARGO-1799 Aggregation page
* ARGO-1807 Investigate and possibly fix additional re-render from changelist to change view
* ARGO-1804 Add breadcrumb navigation
* ARGO-1808 Introduce CRUD for Metric profiles on WEB-API
* ARGO-1806 Add Fontawesome icons
* ARGO-1929 Handle users and groups ACLs
* ARGO-1933 Introduce probe read-only tenant page
* ARGO-1937 Introduce Metric page
* ARGO-1936 History of changes for Probes
* ARGO-1934 Introduce page for API keys handling
* ARGO-1979 Introduce Super Admin POEM
* ARGO-1980 Introduce Probe page on Super Admin POEM
* ARGO-1981 Introduce Metric template page on Super Admin POEM
* ARGO-1991 Create custom Version model to use instead of django-reversion plugin
* ARGO-2012 Limit access to Administration page only to super users
* ARGO-1930 Handle password validation
* ARGO-1992 Clone functionality for Metric templates
* ARGO-2020 History of changes for Metric templates
* ARGO-1940 History of changes for Metrics
* ARGO-1995 Add yum repositories
* ARGO-2030 Metric template change not working properly

### Fixed

* ARGO-1807 Investigate and possibly fix additional re-render from changelist to change view
* ARGO-1836 Session not activated for superuser login
* ARGO-1818 Select flavor in aggregation form 
* ARGO-1923 Create UserProfile when creating Superuser using poem-db tool
* ARGO-2023 Internal group of resources API should be filtered by correct field
* ARGO-2026 Make API key clickable
* ARGO-2031 Fix handling of multiple parameters
* ARGO-2033 Parent field in metric templates shouldn't be required in case of passive metrics

### Changed

* ARGO-1819 Refactor with general HOC and API query components
* ARGO-1884 Merge old poem backend with new poem-2
* ARGO-1939 Refactor internal api views
* ARGO-1959 Update backend Python packages
* ARGO-2011 Refactor GroupOfMetrics model

## [2.3.0] - 2019-04-04
### Added
- ARGO-1573 Back reference fields on metrics and probes pages
- ARGO-1693 Hover dropdown info about selected probe on metric page
- ARGO-1695 Support for deletion of Aggregation profile
- ARGO-1696 Style and arrange Aggregations page
- ARGO-1698 Aggregation profile permissions based on Aggregation group
- ARGO-1700 Introduce config option for specifying WEB-API endpoint
- ARGO-548 Introduce Aggregation profiles CRUD on WEB API
- ARGO-771 POEM multi tenancy support

### Fixed
- ARGO-1719 Fix breadcrumbs for API key templates
- ARGO-1720 Fix Probe change form "Update metric" button
- ARGO-1724 Fix breadcrumb for Delete group pages
- ARGO-1688 Migrations are not registered as applied

### Changed
- ARGO-1653 Refine log entries view
- ARGO-1681 Refactor service type sync to use Django ORM
- ARGO-1694 Refine comments in log entry details page


## [2.2.0] - 2019-02-05
### Added 
- ARGO-1580 Minimal container for tests
- ARGO-1572 Public profiles, probes and metric pages
- ARGO-1524 Introduce services and probes view
- ARGO-1501 Tests for API methods
- ARGO-1449 Add ability to browse all recent actions
- ARGO-1442 Token and session authenticated REST API
- ARGO-1442 Tests for authenticated REST API
- ARGO-1371 Make use of full-blown DBMS

### Fixed
- ARGO-1628 Refine log entries view
- ARGO-1612 Fix tests by creating all needed tables in in-memory-DB
- ARGO-1568 History comments not rendered properly


## [2.1.0] - 2018-11-30
### Added
- ARGO-1497 Publicly available Probes pages
- ARGO-1448 Active/Passive metric designation in metric configuration UI page
- ARGO-1309 Static Metric Config attribute with predefined keys
- ARGO-1370 Optimize connectors queries to POEM
- ARGO-1327 Update probe data without creating new version

### Changed 
- ARGO-1500 Reformat None/NULL field values fetched from DB to empty string in API views
- ARGO-1499 Do not allow probe name changes to existing probe
- ARGO-1485 Sorted autocompletion Metric entries
- ARGO-1482 Allow empty values for keys in metric configuration
- ARGO-1372 Use Apache and mod-wsgi from Software Collections
- ARGO-565 Move to Django 2.0 version

### Fixed
- ARGO-1462 Plaintext LogEntry comments
- ARGO-950 Metric history browse always show most recent changes
