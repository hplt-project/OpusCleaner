export default {
	name: 'DatasetEditor',

	props: {
		datasets: Array
	},

	template: `
		<table>
			<tr v-for="dataset in datasets">
				<td>{{ dataset.name }}</td>
				<td><router-link :to="{name: 'filter-editor', params: {datasetName: dataset.name}}">Filters</router-link></td>
			</tr>
		</table>
	`
}