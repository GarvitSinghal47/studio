import * as getters from './getters';
import * as mutations from './mutations';
import * as actions from './actions';

export default {
  namespaced: true,
  state: () => ({
    channelsMap: {},
    channelDetailsMap: {},
    invitationsMap: {},
    page: {},
  }),
  getters,
  mutations,
  actions,
};