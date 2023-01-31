<template>
	<Teleport to="body">
		<div class="modal-wrapper">
			<div class="overlay" @click="close()"></div>
			<div class="modal">
				<button class="close-button icon-button" title="Close" @click="close()"><XIcon/></button>
				<div class="modal-content">
					<component :is="component" v-bind="$attrs"/>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { shallowRef, watch, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { XIcon } from 'vue3-feather';

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

function close() {
	router.back()
}

function keyListener(e) {
	if (e.keyCode === 27) {
		close()
		e.preventDefault();
	}
}

onMounted(() => {
	document.body.addEventListener('keyup', keyListener)
	document.body.style.overflow = 'hidden';
});

onUnmounted(() => {
	document.body.removeEventListener('keyup', keyListener)
	document.body.style.overflow = '';
});

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
	padding: 4em;
	border: 1px solid #ccc;
	border-radius: 1em;
	box-shadow: 0 0 1em #00000033;
}

.modal-content {
	max-height: calc(100vh - 2*4em - 2*2em);
	overflow-y: auto;
}

.overlay {
	z-index: 1;
	position: absolute;
	width: 100vw;
	height: 100vh;
	background-color: #00000055;
}

.close-button {
	position: absolute;
	top: 1em;
	right: 1em;
}
</style>