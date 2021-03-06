import React, { Component } from 'react';
import { Backend } from './DataManager';
import { Link } from 'react-router-dom';
import {
  LoadingAnim,
  BaseArgoView,
  NotifyOk,
  Checkbox,
  FancyErrorMessage,
  AutocompleteField,
  HistoryComponent,
  DiffElement
} from './UIElements';
import ReactTable from 'react-table';
import {
  FormGroup,
  Label,
  FormText,
  Row,
  Col,
  Button,
  InputGroup,
  InputGroupAddon } from 'reactstrap';
import { Formik, Form, Field } from 'formik';
import { NotificationManager } from 'react-notifications';
import * as Yup from 'yup';


export const ProbeHistory = HistoryComponent('probe');
export const ProbeChange = ProbeComponent();
export const ProbeClone = ProbeComponent(true);


const ProbeSchema = Yup.object().shape({
  name: Yup.string()
    .matches(/^\S*$/, 'Name cannot contain white spaces')
    .required('Required'),
  package: Yup.string()
    .required('Required'),
  repository: Yup.string()
    .url('Invalid url')
    .required('Required'),
  docurl: Yup.string()
    .url('Invalid url')
    .required('Required'),
  description: Yup.string()
    .required('Required'),
  comment: Yup.string()
    .required('Required')
});


const LinkField = ({
  field: { value },
  ...props
}) => (
  <div className='form-control' style={{backgroundColor: '#e9ecef'}}>
    <a href={value}>{value}</a>
  </div>
)


const ProbeForm = ({isTenantSchema=false, isHistory=false,
  errors={name: undefined, package: undefined, repository: undefined, docurl: undefined, comment: undefined},
  state=undefined, addview=false, cloneview=false, list_packages=[], setFieldValue=undefined,
  values=undefined, onSelect=undefined, metrictemplatelist=[]}) =>
  <>
    <FormGroup>
      <Row>
        <Col md={6}>
          <InputGroup>
            <InputGroupAddon addonType='prepend'>Name</InputGroupAddon>
            <Field
              type='text'
              name='name'
              className={`form-control ${errors.name && 'border-danger'}`}
              id='name'
              disabled={isTenantSchema || isHistory}
            />
          </InputGroup>
          {
            errors.name &&
              FancyErrorMessage(errors.name)
          }
          <FormText color="muted">
            Name of this probe.
          </FormText>
        </Col>
        <Col md={2}>
          <InputGroup>
            <InputGroupAddon addonType='prepend'>Version</InputGroupAddon>
            <Field
              type='text'
              name='version'
              className='form-control'
              value={isHistory ? state.version : state.probe.version}
              id='version'
              disabled={true}
            />
          </InputGroup>
          <FormText color="muted">
            Version of the probe.
          </FormText>
        </Col>
        {
          (!addview && !cloneview && !isTenantSchema && !isHistory) &&
            <Col md={2}>
              <Field
                component={Checkbox}
                name='update_metrics'
                className='form-control'
                id='checkbox'
                label='Update metric templates'
              />
              <FormText color='muted'>
                Update all associated metric templates.
              </FormText>
            </Col>
        }
      </Row>
      <Row className='mt-3'>
        <Col md={8}>
          {
            (isTenantSchema || isHistory) ?
              <InputGroup>
                <InputGroupAddon addonType='prepend'>Package</InputGroupAddon>
                <Field
                  type='text'
                  name='package'
                  className='form-control'
                  id='package'
                  disabled={true}
                />
              </InputGroup>
            :
              <>
                <AutocompleteField
                  setFieldValue={setFieldValue}
                  lists={list_packages}
                  icon='packages'
                  field='package'
                  val={values.package}
                  onselect_handler={onSelect}
                  req={errors.package}
                  label='Package'
                />
                {
                  errors.package &&
                    FancyErrorMessage(errors.package)
                }
              </>
          }
          <FormText color='muted'>
            Probe is part of selected package.
          </FormText>
        </Col>
      </Row>
    </FormGroup>
    <FormGroup>
      <h4 className="mt-2 p-1 pl-3 text-light text-uppercase rounded" style={{"backgroundColor": "#416090"}}>Probe metadata</h4>
      <Row className='mt-4 mb-3 align-items-top'>
        <Col md={8}>
          <InputGroup>
            <InputGroupAddon addonType='prepend'>Repository</InputGroupAddon>
            {
              (isTenantSchema || isHistory) ?
                <Field
                  component={LinkField}
                  name='repository'
                  className='form-control'
                  id='repository'
                  disabled={true}
                />
              :
                <Field
                  type='text'
                  name='repository'
                  className={`form-control ${errors.repository && 'border-danger'}`}
                  id='repository'
                />
            }
          </InputGroup>
          {
            errors.repository &&
              FancyErrorMessage(errors.repository)
          }
          <FormText color='muted'>
            Probe repository URL.
          </FormText>
        </Col>
      </Row>
      <Row className='mb-3 align-items-top'>
        <Col md={8}>
          <InputGroup>
            <InputGroupAddon addonType='prepend'>Documentation</InputGroupAddon>
            {
              (isTenantSchema || isHistory) ?
                <Field
                  component={LinkField}
                  name='docurl'
                  className='form-control'
                  id='docurl'
                  disabled={true}
                />
              :
                <Field
                  type='text'
                  name='docurl'
                  className={`form-control ${errors.docurl && 'border-danger'}`}
                  id='docurl'
                />
            }
          </InputGroup>
          {
            errors.docurl &&
              FancyErrorMessage(errors.docurl)
          }
          <FormText color='muted'>
            Documentation URL.
          </FormText>
        </Col>
      </Row>
      <Row className='mb-3 align-items-top'>
        <Col md={8}>
          <Label for='description'>Description</Label>
          <Field
            component='textarea'
            name='description'
            rows='15'
            className={`form-control ${errors.description && 'border-danger'}`}
            id='description'
            disabled={isTenantSchema || isHistory}
          />
          {
            errors.description &&
              FancyErrorMessage(errors.description)
          }
          <FormText color='muted'>
            Free text description outlining the purpose of this probe.
          </FormText>
        </Col>
      </Row>
      <Row className='mb-3 align-items-top'>
        <Col md={8}>
          <Label for='comment'>Comment</Label>
          <Field
            component='textarea'
            name='comment'
            rows='5'
            className={`form-control ${errors.comment && 'border-danger'}`}
            id='comment'
            disabled={isTenantSchema || isHistory}
          />
          {
            errors.comment &&
              FancyErrorMessage(errors.comment)
          }
          <FormText color='muted'>
            Short comment about this version.
          </FormText>
        </Col>
      </Row>
      {
        (!isTenantSchema && !isHistory && !addview && !cloneview) &&
          <Row>
            <Col md={8}>
              <div>
                Metric templates:
                {
                  metrictemplatelist.length > 0 &&
                    <div>
                      {
                        metrictemplatelist
                          .map((e, i) => <Link key={i} to={`/ui/metrictemplates/${e}`}>{e}</Link>)
                          .reduce((prev, curr) => [prev, ', ', curr])
                      }
                    </div>
                }
              </div>
            </Col>
          </Row>
      }
    </FormGroup>
  </>


export class ProbeList extends Component {
  constructor(props) {
    super(props);

    this.location = props.location;

    this.state = {
      loading: false,
      list_probe: null,
      isTenantSchema: null,
      search_name: '',
      search_description: '',
      search_package: ''
    };

    this.backend = new Backend();
  }

  componentDidMount() {
    this.setState({loading: true});

    Promise.all([
      this.backend.fetchData('/api/v2/internal/probes'),
      this.backend.isTenantSchema()
    ]).then(([json, isTenantSchema]) =>
        this.setState({
          list_probe: json,
          isTenantSchema: isTenantSchema,
          loading: false,
          search_name: ''
        }))
  }

  render() {
    const columns = [
      {
        Header: '#',
        id: 'row',
        minWidth: 12,
        Cell: (row) =>
          <div style={{textAlign: 'center'}}>
            {row.index + 1}
          </div>
      },
      {
        Header: 'Name',
        id: 'name',
        minWidth: 80,
        accessor: e =>
          <Link to={`/ui/probes/${e.name}`}>
            {e.name}
          </Link>,
        filterable: true,
        Filter: (
          <input
            value={this.state.search_name}
            onChange={e => this.setState({search_name: e.target.value})}
            placeholder='Search by name'
            style={{width: "100%"}}
          />
        )
      },
      {
        Header: '#versions',
        id: 'nv',
        minWidth: 25,
        accessor: e =>
          <Link to={`/ui/probes/${e.name}/history`}>
            {e.nv}
          </Link>,
        Cell: row =>
          <div style={{textAlign: 'center'}}>
            {row.value}
          </div>
      },
      {
        Header: 'Package',
        minWidth: 120,
        accessor: 'package',
        filterable: true,
        Filter: (
          <input
            type='text'
            placeholder='Search by package'
            value={this.state.search_package}
            onChange={e => this.setState({search_package: e.target.value})}
            style={{width: '100%'}}
          />
        ),
        filterMethod:
          (filter, row) =>
            row[filter.id] !== undefined ? String(row[filter.id]).toLowerCase().includes(filter.value.toLowerCase()) : true
      },
      {
        Header: 'Description',
        minWidth: 200,
        accessor: 'description',
        filterable: true,
        Filter: (
          <input
            type='text'
            placeholder='Search by description'
            value={this.state.search_description}
            onChange={e=> this.setState({search_description: e.target.value})}
            style={{width: '100%'}}
          />
        ),
        filterMethod:
          (filter, row) =>
            row[filter.id] !== undefined ? String(row[filter.id]).toLowerCase().includes(filter.value.toLowerCase()) : true
      }
    ];

    var { isTenantSchema, list_probe, loading } = this.state;

    if (this.state.search_name) {
      list_probe = list_probe.filter(row =>
        row.name.toLowerCase().includes(this.state.search_name.toLowerCase())
      );
    }

    if (this.state.search_description) {
      list_probe = list_probe.filter(row =>
        row.description.toLowerCase().includes(this.state.search_description.toLowerCase())
      );
    }

    if (this.state.search_package) {
      list_probe = list_probe.filter(row =>
        row.package.toLowerCase().includes(this.state.search_package.toLowerCase())
      );
    }

    if (loading)
      return (<LoadingAnim />);

    else if (!loading && list_probe) {
      return (
        <BaseArgoView
          resourcename='probe'
          location={this.location}
          listview={true}
          addnew={!isTenantSchema}
        >
          <ReactTable
            data={list_probe}
            columns={columns}
            className='-highlight'
            defaultPageSize={50}
            rowsText='probes'
            getTheadThProps={() => ({className: 'table-active font-weight-bold p-2'})}
          />
        </BaseArgoView>
      );
    } else
      return null;
  }
}


function ProbeComponent(cloneview=false) {
  return class extends Component {
    constructor(props) {
      super(props);

      this.name = props.match.params.name;
      this.addview = props.addview;
      this.location = props.location;
      this.history = props.history;
      this.backend = new Backend();

      this.state = {
        probe: {
          'id': '',
          'name': '',
          'version': '',
          'package': '',
          'repository': '',
          'docurl': '',
          'description': '',
          'comment': ''
        },
        isTenantSchema: null,
        metrictemplatelist: [],
        list_packages: [],
        validationVisible: true,
        update_metrics: false,
        loading: false,
        areYouSureModal: false,
        modalFunc: undefined,
        modalTitle: undefined,
        modalMsg: undefined
      };

      this.toggleAreYouSure = this.toggleAreYouSure.bind(this);
      this.toggleAreYouSureSetModal = this.toggleAreYouSureSetModal.bind(this);
      this.onSubmitHandle = this.onSubmitHandle.bind(this);
      this.doDelete = this.doDelete.bind(this);
      this.onDismiss = this.onDismiss.bind(this);
      this.onSelect = this.onSelect.bind(this);
    }

    toggleAreYouSure() {
      this.setState(prevState =>
        ({areYouSureModal: !prevState.areYouSureModal}));
    }

    toggleAreYouSureSetModal(msg, title, onyes) {
      this.setState(prevState =>
        ({areYouSureModal: !prevState.areYouSureModal,
          modalFunc: onyes,
          modalMsg: msg,
          modalTitle: title,
        }));
    }

    onSubmitHandle(values, actions) {
      let msg = undefined;
      let title = undefined;

      if (this.addview || cloneview) {
        msg = 'Are you sure you want to add probe?';
        title = 'Add probe';
      } else {
          msg = 'Are you sure you want to change probe?';
          title = 'Change probe';
      }

      this.toggleAreYouSureSetModal(msg, title,
        () => this.doChange(values, actions));
    }

    doChange(values, actions) {
      if (this.addview || cloneview) {
        let cloned_from = undefined;
        if (cloneview) {
          cloned_from = values.id;
        } else {
          cloned_from = '';
        }
        this.backend.addObject(
          '/api/v2/internal/probes/',
          {
            name: values.name,
            package: values.package,
            repository: values.repository,
            docurl: values.docurl,
            description: values.description,
            comment: values.comment,
            cloned_from: cloned_from
          }
          ).then(response => {
            if (!response.ok) {
              response.json()
                .then(json => {
                  NotificationManager.error(json.detail, 'Error');
                });
            } else {
              NotifyOk({
                msg: 'Probe successfully added',
                title: 'Added',
                callback: () => this.history.push('/ui/probes')
              });
            }
          });
      } else {
        this.backend.changeObject(
          '/api/v2/internal/probes/',
          {
            id: values.id,
            name: values.name,
            package: values.package,
            repository: values.repository,
            docurl: values.docurl,
            description: values.description,
            comment: values.comment,
            update_metrics: values.update_metrics
          }
        ).then(response => {
            if (!response.ok) {
              response.json()
                .then(json => {
                  NotificationManager.error(json.detail, 'Error');
                });
            } else {
              NotifyOk({
                msg: 'Probe successfully changed',
                title: 'Changed',
                callback: () => this.history.push('/ui/probes')
              });
            }
          });
      }
    }

    doDelete(name) {
      this.backend.deleteObject(`/api/v2/internal/probes/${name}`)
        .then(response => {
          if (!response.ok) {
            response.json()
              .then(json => {
                NotificationManager.error(json.detail, 'Error');
              });
          } else {
            NotifyOk({
              msg: 'Probe successfully deleted',
              title: 'Deleted',
              callback: () => this.history.push('/ui/probes')
            });
          }
        });
    }

    onDismiss() {
      this.setState({ validationVisible: false });
    }

    onSelect(field, value) {
      let probe = this.state.probe;
      probe[field] = value;
      probe['version'] = value.split(' ')[1].slice(1, -1);
      this.setState({probe: probe});
    }

    componentDidMount() {
      this.setState({loading: true});

      Promise.all([
        this.backend.isTenantSchema(),
        this.backend.fetchData('/api/v2/internal/packages')
      ])
        .then(([isTenantSchema, pkgs]) => {
          let list_packages = [];
          pkgs.forEach(e => list_packages.push(`${e.name} (${e.version})`));
          if (!this.addview) {
            this.backend.fetchData(`/api/v2/internal/probes/${this.name}`)
              .then(probe => {
                this.backend.fetchData(`/api/v2/internal/metricsforprobes/${probe.name}(${probe.version})`)
                  .then(metrics => {
                    this.setState({
                      probe: probe,
                      list_packages: list_packages,
                      isTenantSchema: isTenantSchema,
                      metrictemplatelist: metrics,
                      loading: false
                    });
                  });
              });
          } else {
            this.setState({
              list_packages: list_packages,
              isTenantSchema: isTenantSchema,
              loading: false
            });
          }
        });
    }

    render() {
      const { probe, update_metrics, isTenantSchema, metrictemplatelist,
        list_packages, loading } = this.state;

      if (loading)
        return(<LoadingAnim/>)

      else if (!loading) {
        if (!isTenantSchema) {
          return (
            <BaseArgoView
              resourcename='probe'
              location={this.location}
              addview={this.addview}
              cloneview={cloneview}
              clone={true}
              modal={true}
              state={this.state}
              toggle={this.toggleAreYouSure}>
              <Formik
                initialValues = {{
                  id: probe.id,
                  name: probe.name,
                  version: probe.version,
                  package: probe.package,
                  repository: probe.repository,
                  docurl: probe.docurl,
                  description: probe.description,
                  comment: probe.comment,
                  update_metrics: update_metrics
                }}
                validationSchema={ProbeSchema}
                onSubmit = {(values, actions) => this.onSubmitHandle(values, actions)}
              >
                {props => (
                  <Form>
                    <ProbeForm
                      {...props}
                      state={this.state}
                      addview={this.addview}
                      cloneview={cloneview}
                      list_packages={list_packages}
                      onSelect={this.onSelect}
                      metrictemplatelist={metrictemplatelist}
                    />
                    {
                      <div className="submit-row d-flex align-items-center justify-content-between bg-light p-3 mt-5">
                        {
                          (!this.addview && !cloneview) ?
                            <Button
                              color='danger'
                              onClick={() => {
                                this.toggleAreYouSureSetModal(
                                  'Are you sure you want to delete probe?',
                                  'Delete probe',
                                  () => this.doDelete(props.values.name)
                                )}}
                            >
                              Delete
                            </Button>
                          :
                            <div></div>
                        }
                        <Button
                          color='success'
                          id='submit-button'
                          type='submit'
                        >
                          Save
                        </Button>
                      </div>
                  }
                  </Form>
                )}
              </Formik>
            </BaseArgoView>
          )
        } else {
          return (
            <BaseArgoView
              resourcename='Probe details'
              location={this.location}
              tenantview={true}
              history={true}
            >
              <Formik
                initialValues = {{
                  id: probe.id,
                  name: probe.name,
                  version: probe.version,
                  package: probe.package,
                  repository: probe.repository,
                  docurl: probe.docurl,
                  description: probe.description,
                  comment: probe.comment
                }}
                render = {props => (
                  <ProbeForm
                    {...props}
                    isTenantSchema={true}
                    state={this.state}
                  />
                )}
              />
            </BaseArgoView>
          );
        }
      }
    }
  };
}


export class ProbeVersionCompare extends Component{
  constructor(props) {
    super(props);

    this.version1 = props.match.params.id1;
    this.version2 = props.match.params.id2;
    this.name = props.match.params.name;

    this.state = {
      loading: false,
      name1: '',
      version1: '',
      package1: '',
      description1: '',
      repository1: '',
      docurl1: '',
      comment1: '',
      name2: '',
      version2: '',
      package2: '',
      description2: '',
      repository2: '',
      docurl2: '',
      comment2: ''
    };

    this.backend = new Backend();
  }

  componentDidMount() {
    this.setState({loading: true});

    this.backend.fetchData(`/api/v2/internal/version/probe/${this.name}`)
      .then((json) => {
        let name1 = '';
        let version1 = '';
        let package1 = '';
        let description1 = '';
        let repository1 = '';
        let docurl1 = '';
        let comment1 = '';
        let name2 = ''
        let version2 = '';
        let package2 = '';
        let description2 = '';
        let repository2 = '';
        let docurl2 = '';
        let comment2 = '';

        json.forEach((e) => {
          if (e.version == this.version1) {
            name1 = e.fields.name;
            version1 = e.fields.version;
            package1 = e.fields.package;
            description1 = e.fields.description;
            repository1 = e.fields.repository;
            docurl1 = e.fields.docurl;
            comment1 = e.fields.comment;
          } else if (e.version === this.version2) {
            name2 = e.fields.name;
            version2 = e.fields.version;
            package2 = e.fields.package;
            description2 = e.fields.description;
            repository2 = e.fields.repository;
            docurl2 = e.fields.docurl;
            comment2 = e.fields.comment;
          }
        });

        this.setState({
          name1: name1,
          version1: version1,
          package1: package1,
          description1: description1,
          repository1: repository1,
          docurl1: docurl1,
          comment1: comment1,
          name2: name2,
          version2: version2,
          package2: package2,
          description2: description2,
          repository2: repository2,
          docurl2: docurl2,
          comment2: comment2,
          loading: false
        });
      }
    )
  }

  render() {
    var { name1, name2, version1, version2, package1, package2,
      description1, description2, repository1, repository2,
      docurl1, docurl2, comment1, comment2, loading } = this.state;

    if (loading)
      return (<LoadingAnim/>);

    else if (!loading && name1 && name2) {
      return (
        <React.Fragment>
          <div className="d-flex align-items-center justify-content-between">
            <h2 className='ml-3 mt-1 mb-4'>{'Compare ' + this.name}</h2>
          </div>
          {
            (name1 !== name2) &&
              <DiffElement title='name' item1={name1} item2={name2}/>
          }

          {
            (version1 !== version2) &&
              <DiffElement title='version' item1={version1} item2={version2}/>
          }

          {
            (package1 !== package2) &&
              <DiffElement title='package' item1={package1} item2={package2}/>
          }

          {
            (description1 !== description2) &&
              <DiffElement title='description' item1={description1} item2={description2}/>
          }

          {
            (repository1 !== repository2) &&
              <DiffElement title='repository' item1={repository1} item2={repository2}/>
          }

          {
            (docurl1 !== docurl2) &&
              <DiffElement title={'documentation'} item1={docurl1} item2={docurl2}/>
          }
          {
            (comment1 !== comment2) &&
              <DiffElement title={'comment'} item1={comment1} item2={comment2}/>
          }
        </React.Fragment>
      );
    }
    else
      return null;
  }
}


export class ProbeVersionDetails extends Component {
  constructor(props) {
    super(props);

    this.name = props.match.params.name;
    this.version = props.match.params.version;

    this.backend = new Backend();

    this.state = {
      name: '',
      version: '',
      pkg: '',
      description: '',
      repository: '',
      docurl: '',
      comment: '',
      loading: false
    };
  }

  componentDidMount() {
    this.setState({loading: true});

    this.backend.fetchData(`/api/v2/internal/version/probe/${this.name}`)
      .then((json) => {
        json.forEach((e) => {
          if (e.version === this.version)
            this.setState({
              name: e.fields.name,
              version: e.fields.version,
              pkg: e.fields.package,
              description: e.fields.description,
              repository: e.fields.repository,
              docurl: e.fields.docurl,
              comment: e.fields.comment,
              loading: false
            });
        });
      }
    )
  }

  render() {
    const { name, version, pkg, description, repository,
      docurl, comment, loading} = this.state;

    if (loading)
      return (<LoadingAnim/>);

    else if (!loading && name) {
      return (
        <BaseArgoView
          resourcename={`${name} (${version})`}
          infoview={true}
        >
          <Formik
            initialValues = {{
              name: name,
              version: version,
              package: pkg,
              repository: repository,
              docurl: docurl,
              description: description,
              comment: comment
            }}
            render = {props => (
              <ProbeForm
                {...props}
                state={this.state}
                isHistory={true}
              />
            )}
          />
        </BaseArgoView>
      );
    }
    else
      return null;
  }
}
