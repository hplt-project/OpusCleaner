import { h, defineComponent } from "vue";
import {diff} from "diff";

export default defineComponent({
	name: 'inlinediff',

	props: {
		current: {
			type: String,
			required: true
		},
		previous: {
			type: String,
			required: true
		}
	},

	computed: {
		mutations() {
			return diff(this.previous.split(''), this.current.split(''), {
				equals: (a,b) => a == b,
				maxEditLength: Math.max(this.previous.length, this.current.length) * 0.5
			});
		}
	},

	render() {
		if (!this.mutations) {
			return h('span', {}, [
				h('del', {}, [this.previous]),
				h('ins', {}, [this.current])
			]);
		}

		return h('span', {}, this.mutations.map(mutation => {
			if (mutation.added || mutation.removed)
				return h(mutation.added ? 'ins' : 'del', {}, mutation.value.join(''));
			else
				return mutation.value.join('');
		}));
	},
})
