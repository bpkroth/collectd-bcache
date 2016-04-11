# collectd-bcache

This script collects [bcache](http://bcache.evilpiepirate.org/) SSD caching statistics and outputs it to the collectd daemon process via the [Collectd Python plugin](https://collectd.org/wiki/index.php/Plugin:Python).

## Usage

### Collectd

```
LoadPlugin "python"
<Plugin "python">
	ModulePath "/etc/collectd/libexec/"

	Import "bcache"
	<Module "bcache">
		#Verbose true
	</Module>
</Plugin>
```
