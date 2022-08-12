export default {
	name: 'DatasetEditor',

	props: {
		datasets: Array
	},

	methods: {
		getLanguages(dataset) {
			return Object.keys(dataset.columns)
		}
	},

	template: `
		<table>
			<tr v-for="dataset in datasets">
				<td>{{ dataset.name }}</td>
				<td>{{ getLanguages(dataset).join(', ') }}</td>
				<td><router-link :to="{name: 'filter-editor', params: {datasetName: dataset.name}}">Filters</router-link></td>
			</tr>
		</table>
	`
}