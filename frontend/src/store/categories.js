import {reactive} from 'vue';

const data = reactive({
	categories: [],
	mapping: {}
});

async function fetchCategories() {
	const response = await fetch('/api/categories/');
	return await response.json();
}

let request = null;

export function getCategories() {
	if (!request)
		request = fetchCategories().then(remote => Object.assign(data, remote));

	return data
}

export function getCategoriesForDataset(dataset) {
	const data = getCategories();

	// Look through all mappings, and return the category objects if the dataset
	// name is mentioned in the mapping section for it.
	return Object.entries(data.mapping).reduce((acc, [name, datasets]) => {
		if (datasets.includes(dataset.name))
			return [...acc, data.categories.find(category => category.name == name)]
		else
			return acc
	}, []);
}
