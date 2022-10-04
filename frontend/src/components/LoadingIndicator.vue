<script setup functional>
const labels = {
	'pending': 'Pending…',
	'loading': 'Loading…',
	'loaded': 'Loaded',
	'failed': 'Failed',
};

const {state} = defineProps({
	state: {
		type: String,
		required: true,
		validator(val) {
			return ['pending', 'loading', 'loaded', 'failed'].includes(val);
		}
	}
})
</script>

<template>
	<span class="loading-indicator" :class="state" :title="labels[state]"></span>
</template>

<style>
@keyframes spin { 
    100% { 
        -webkit-transform: rotate(360deg); 
        transform:rotate(360deg); 
    } 
}

.loading-indicator {
	display: inline-block;
	width: 1em;
	height: 1em;
}

.loading-indicator::after {
	content: '';
	display: inline-block;
	overflow: hidden;
	text-indent: 2em;
	width: 1em;
	height: 1em;
	border: 2px solid currentColor;
	border-radius: 50%;
	line-height: 1;
	text-indent: 0;
	text-align: center;
}

.loading-indicator.loaded::after {
	content: '✔';
}

.loading-indicator.failed::after {
	content: '⨯';
}

.loading-indicator.loading::after {
	border-right-color: transparent;
	animation: spin 1s linear infinite;
}

.loading-indicator.pending::after {
	border-style: dotted;
}
</style>