<template>
	<Teleport to="body">
		<div class="modal-wrapper">
			<div class="overlay" @click="router.back()"></div>
			<div class="modal">
				<!-- you can use v-bind to pass down all props -->
				<component :is="component" v-bind="$attrs"/>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { shallowRef, watch, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';

function isESModule(obj) {
	return obj.__esModule || obj[Symbol.toStringTag] === 'Module';
}

// Accept a component="" attribute, which can be either a Vue component, or
// a promise that resolves to one, or a promise that resolves to a module with
// the default exported value being the component. That last one allows us to do
// `<Modal :component="import('somecomponent.vue')" />`.
const props = defineProps(['component']);

// The real sub-component (once it is loaded)
const component = shallowRef();

// Watch the component property change. If it is a promise, deal with the
// async loading. Copy the resolved component to `component`.
watch(props.component, async (val, old, onCleanup) => {	
	component.value = null;
	
	let cancel = new Promise((accept, reject) => {
		onCleanup(reject);
	});
	
	const value = await Promise.race([Promise.resolve(val), cancel]);
	component.value = isESModule(value) ? value.default : value;
}, {immediate: true});

const router = useRouter();

function keyListener(e) {
	if (e.keyCode === 27) {
		router.back()
		e.preventDefault();
	}
}

onMounted(() => document.body.addEventListener('keyup', keyListener));

onUnmounted(() => document.body.removeEventListener('keyup', keyListener));

</script>

<style scoped>
.modal-wrapper {
	position: fixed;
	top: 0;
	left: 0;
	width: 100vw;
	height: 100vh;
}
.modal {
	position: absolute;
	z-index: 1;
	margin: auto;
	left: 50%;
	top: 50%;
	transform: translate(-50%, -50%);
	background-color: white;
	padding: 5em;
	border: 1px solid #ccc;
	border-radius: 1em;
	box-shadow: 0 0 1em #00000033;
}

.overlay {
	z-index: 1;
	position: absolute;
	width: 100vw;
	height: 100vh;
	background-color: #00000055;
}
</style>