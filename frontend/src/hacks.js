import {watchEffect, ref, unref} from 'vue';

let uid = 0;

export function getUniqueId() {
	return ++uid;
}

export function fetched(fn) {
	const val = ref();

	watchEffect((onCleanup) => {
		const fetcher = (url, options) => {
			const abort = new AbortController();
			onCleanup(() => abort.abort());

			const signal = abort.signal;
			return fetch(url, {...options, signal});
		};

		Promise.resolve(fn(fetcher)).then(out => {
			val.value = out
		});
	});

	return val;
}
